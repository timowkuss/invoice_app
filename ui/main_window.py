"""
ui/main_window.py

Главное окно приложения. Собирает вместе все виджеты (превью,
таблицу товаров), запускает OCR в фоновом потоке и обрабатывает
экспорт в Excel и работу с историей документов.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config.config import APP_NAME, APP_VERSION, JSON_DRAFTS_DIR, SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_PDF_EXTENSIONS
from config.settings import SettingsManager
from database.db_manager import DatabaseManager
from excel.exporter import ExcelExporter
from json_exporter import load_draft, save_draft
from models.document import DocumentRecord
from ui.dialogs.camera_dialog import CameraDialog
from ui.dialogs.history_dialog import HistoryDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.widgets.preview_widget import PreviewWidget
from ui.widgets.table_widget import ProductTableWidget
from ui.workers.ocr_worker import OcrWorker
from utils.file_utils import generate_export_path, is_pdf_file

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Главное окно приложения для распознавания товарных накладных."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 800)

        self._settings_manager = SettingsManager()
        self._db_manager = DatabaseManager()
        self._exporter = ExcelExporter()

        self._current_file_path: str | None = None
        self._current_json_path: str | None = None
        self._ocr_worker: OcrWorker | None = None

        self._build_ui()
        self._apply_theme(self._settings_manager.settings.theme)

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)

        root_layout.addLayout(self._build_top_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._preview_widget = PreviewWidget()
        self._table_widget = ProductTableWidget()
        self._table_widget.setEnabled(False)

        left_panel = self._wrap_in_frame(self._preview_widget, "Предпросмотр документа")
        right_panel = self._wrap_in_frame(self._table_widget, "Распознанные товары")

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 780])
        root_layout.addWidget(splitter, stretch=1)

        root_layout.addLayout(self._build_bottom_toolbar())

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        root_layout.addWidget(self._progress_bar)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self._status_label = QLabel("Готово к работе")
        status_bar.addWidget(self._status_label)

    @staticmethod
    def _wrap_in_frame(widget: QWidget, title: str) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #444;")
        layout.addWidget(title_label)
        layout.addWidget(widget, stretch=1)
        return frame

    def _build_top_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_camera = self._make_big_button("📷  Сделать фото")
        self._btn_camera.clicked.connect(self._on_take_photo)

        self._btn_pdf = self._make_big_button("📂  Открыть PDF")
        self._btn_pdf.clicked.connect(self._on_open_pdf)

        self._btn_image = self._make_big_button("🖼  Открыть изображение")
        self._btn_image.clicked.connect(self._on_open_image)

        self._btn_history = self._make_big_button("📑  История")
        self._btn_history.clicked.connect(self._on_open_history)

        self._btn_load_draft = self._make_big_button("📋  Загрузить черновик")
        self._btn_load_draft.clicked.connect(self._on_load_draft)

        self._btn_settings = self._make_big_button("⚙  Настройки")
        self._btn_settings.clicked.connect(self._on_open_settings)

        for button in (self._btn_camera, self._btn_pdf, self._btn_image, self._btn_history, self._btn_load_draft, self._btn_settings):
            layout.addWidget(button)

        return layout

    def _build_bottom_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._btn_recognize = QPushButton("🔎 Распознать")
        self._btn_recognize.clicked.connect(self._on_recognize_clicked)
        self._btn_recognize.setEnabled(False)

        self._btn_edit = QPushButton("✏ Редактировать")
        self._btn_edit.clicked.connect(self._on_edit_clicked)
        self._btn_edit.setEnabled(False)

        self._btn_export = QPushButton("📤 Экспорт в Excel")
        self._btn_export.clicked.connect(self._on_export_clicked)
        self._btn_export.setEnabled(False)

        self._btn_clear = QPushButton("🧹 Очистить")
        self._btn_clear.clicked.connect(self._on_clear_clicked)

        for button in (self._btn_recognize, self._btn_edit, self._btn_export, self._btn_clear):
            button.setMinimumHeight(38)
            layout.addWidget(button)

        return layout

    @staticmethod
    def _make_big_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumHeight(56)
        button.setMinimumWidth(160)
        button.setStyleSheet("font-size: 13px;")
        return button

    def _apply_theme(self, theme: str) -> None:
        if theme == "dark":
            self.setStyleSheet(
                """
                QMainWindow, QWidget { background-color: #1e1f24; color: #e8e8e8; }
                QPushButton { background-color: #2c2e36; color: #e8e8e8; border: 1px solid #3d3f48; border-radius: 6px; padding: 6px; }
                QPushButton:hover { background-color: #383b45; }
                QPushButton:disabled { color: #6b6d75; }
                QFrame { background-color: #24262c; border-radius: 8px; }
                QTableWidget { background-color: #1e1f24; gridline-color: #3d3f48; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QPushButton { background-color: #ffffff; border: 1px solid #d6d9de; border-radius: 6px; padding: 6px; }
                QPushButton:hover { background-color: #f0f2f5; }
                QPushButton:disabled { color: #a3a6ad; }
                QFrame { background-color: #ffffff; border-radius: 8px; border: 1px solid #e5e7eb; }
                """
            )

    # ------------------------------------------------------------------
    # Загрузка документов
    # ------------------------------------------------------------------
    def _on_take_photo(self) -> None:
        dialog = CameraDialog(self)
        if dialog.exec() == CameraDialog.DialogCode.Accepted and dialog.captured_path:
            self._load_file(dialog.captured_path)

    def _on_open_pdf(self) -> None:
        extensions = " ".join(f"*{ext}" for ext in SUPPORTED_PDF_EXTENSIONS)
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть PDF", "", f"PDF файлы ({extensions})")
        if file_path:
            self._load_file(file_path)

    def _on_open_image(self) -> None:
        extensions = " ".join(f"*{ext}" for ext in SUPPORTED_IMAGE_EXTENSIONS)
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть изображение", "", f"Изображения ({extensions})")
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str) -> None:
        self._current_file_path = file_path
        path = Path(file_path)

        if is_pdf_file(path):
            self._preview_widget.set_image_from_path("")  # очистка
            try:
                from ocr.pdf_converter import PdfConverter

                pages = PdfConverter().pdf_to_images(str(path))
                if pages:
                    self._preview_widget.set_image_from_array(pages[0])
            except Exception as exc:  # noqa: BLE001
                logger.error("Не удалось построить предпросмотр PDF: %s", exc)
                self._status_label.setText("Не удалось построить предпросмотр PDF")
        else:
            self._preview_widget.set_image_from_path(str(path))

        self._btn_recognize.setEnabled(True)
        self._status_label.setText(f"Загружен файл: {path.name}")

    # ------------------------------------------------------------------
    # Распознавание
    # ------------------------------------------------------------------
    def _on_recognize_clicked(self) -> None:
        if not self._current_file_path:
            return

        self._set_processing_state(True)
        settings = self._settings_manager.settings

        self._ocr_worker = OcrWorker(
            file_path=self._current_file_path,
            languages=settings.ocr_languages,
            use_gpu=settings.ocr_gpu,
            ocr_engine=settings.ocr_engine,
            mistral_api_key=settings.mistral_api_key,
        )
        self._ocr_worker.progress_changed.connect(self._on_progress_changed)
        self._ocr_worker.finished_ok.connect(self._on_recognition_finished)
        self._ocr_worker.finished_error.connect(self._on_recognition_error)
        self._ocr_worker.start()

    def _on_progress_changed(self, percent: int, message: str) -> None:
        self._progress_bar.setValue(percent)
        self._status_label.setText(message)

    def _on_recognition_finished(self, products: list) -> None:
        self._set_processing_state(False)
        self._table_widget.setEnabled(True)
        self._table_widget.load_products(products)
        self._btn_edit.setEnabled(True)
        self._btn_export.setEnabled(bool(products))
        self._status_label.setText(f"Распознано товаров: {len(products)}")

        if not products:
            QMessageBox.information(
                self,
                "Товары не найдены",
                "Не удалось распознать ни одной строки товаров. "
                "Попробуйте сделать более четкое фото или добавить строки вручную.",
            )
            return

        # Автосохранение черновика в JSON после OCR
        source_name = Path(self._current_file_path).name if self._current_file_path else ""
        try:
            json_path = save_draft(products, source_filename=source_name)
            self._current_json_path = str(json_path)
            self._status_label.setText(
                f"Распознано: {len(products)} товаров | Черновик: {Path(json_path).name}"
            )
        except OSError as exc:
            logger.error("Не удалось сохранить JSON-черновик: %s", exc)

    def _on_recognition_error(self, message: str) -> None:
        self._set_processing_state(False)
        QMessageBox.critical(self, "Ошибка распознавания", f"Не удалось обработать документ:\n{message}")
        self._status_label.setText("Ошибка распознавания")

    def _set_processing_state(self, processing: bool) -> None:
        self._progress_bar.setVisible(processing)
        self._progress_bar.setValue(0)
        for button in (
            self._btn_recognize,
            self._btn_camera,
            self._btn_pdf,
            self._btn_image,
            self._btn_clear,
            self._btn_export,
        ):
            button.setEnabled(not processing)
        if not processing:
            self._btn_recognize.setEnabled(self._current_file_path is not None)

    # ------------------------------------------------------------------
    # Редактирование / экспорт / очистка
    # ------------------------------------------------------------------
    def _on_edit_clicked(self) -> None:
        self._table_widget.setEnabled(True)
        self._table_widget._table.setEditTriggers(  # noqa: SLF001 - осознанный доступ внутри пакета ui
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._status_label.setText("Режим редактирования: дважды щелкните по ячейке для изменения")

    def _on_export_clicked(self) -> None:
        products = self._table_widget.get_products()
        if not products:
            QMessageBox.information(self, "Нет данных", "Таблица товаров пуста — нечего экспортировать.")
            return

        settings = self._settings_manager.settings
        output_path = generate_export_path(Path(settings.export_folder))

        try:
            self._exporter.export(products, output_path)
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка экспорта", f"Не удалось сохранить Excel-файл:\n{exc}")
            return

        # Обновляем JSON-черновик с текущими данными из таблицы
        source_name = Path(self._current_file_path).name if self._current_file_path else ""
        try:
            if self._current_json_path:
                json_path = save_draft(products, source_filename=source_name, output_path=Path(self._current_json_path))
            else:
                json_path = save_draft(products, source_filename=source_name)
                self._current_json_path = str(json_path)
        except OSError as exc:
            logger.warning("Не удалось обновить JSON-черновик: %s", exc)

        record = DocumentRecord.create_now(
            supplier="",
            source_filename=source_name,
            items_count=len(products),
            excel_path=str(output_path),
        )
        self._db_manager.add_record(record)

        self._status_label.setText(f"Экспортировано в {output_path}")
        QMessageBox.information(self, "Готово", f"Excel-файл сохранен:\n{output_path}")

        if settings.auto_open_excel:
            self._open_file_with_system_default(output_path)

    @staticmethod
    def _open_file_with_system_default(path: Path) -> None:
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError as exc:
            logger.error("Не удалось открыть файл %s: %s", path, exc)

    def _on_clear_clicked(self) -> None:
        self._current_file_path = None
        self._current_json_path = None
        self._preview_widget.clear()
        self._table_widget.clear()
        self._table_widget.setEnabled(False)
        self._btn_recognize.setEnabled(False)
        self._btn_edit.setEnabled(False)
        self._btn_export.setEnabled(False)
        self._status_label.setText("Готово к работе")

    # ------------------------------------------------------------------
    # Загрузка JSON-черновика
    # ------------------------------------------------------------------
    def _on_load_draft(self) -> None:
        """Загружает JSON-черновик и заполняет таблицу товарами."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить JSON-черновик", str(JSON_DRAFTS_DIR), "JSON файлы (*.json)"
        )
        if not file_path:
            return

        try:
            products = load_draft(Path(file_path))
        except (FileNotFoundError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить черновик:\n{exc}")
            return

        self._current_json_path = file_path
        self._table_widget.setEnabled(True)
        self._table_widget.load_products(products)
        self._btn_edit.setEnabled(True)
        self._btn_export.setEnabled(bool(products))
        self._status_label.setText(f"Загружен черновик: {Path(file_path).name} ({len(products)} товаров)")

    # ------------------------------------------------------------------
    # Диалоги
    # ------------------------------------------------------------------
    def _on_open_history(self) -> None:
        dialog = HistoryDialog(self._db_manager, self)
        dialog.exec()

    def _on_open_settings(self) -> None:
        dialog = SettingsDialog(self._settings_manager, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._apply_theme(self._settings_manager.settings.theme)

    def closeEvent(self, event) -> None:  # noqa: N802 - имя метода задано Qt
        if self._ocr_worker is not None and self._ocr_worker.isRunning():
            self._ocr_worker.terminate()
            self._ocr_worker.wait()
        super().closeEvent(event)
