"""
ui/dialogs/history_dialog.py

Диалоговое окно истории обработанных документов. Позволяет
просмотреть список ранее распознанных накладных и открыть
соответствующий Excel-файл.
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
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QDialog,
)

from database.db_manager import DatabaseManager
from models.document import DocumentRecord

logger = logging.getLogger(__name__)

_COLUMNS = ("Дата", "Поставщик", "Файл-источник", "Товаров", "Excel")


class HistoryDialog(QDialog):
    """Показывает историю обработанных накладных из SQLite базы данных."""

    def __init__(self, db_manager: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📑 История документов")
        self.resize(760, 420)

        self._db_manager = db_manager
        self._records: list[DocumentRecord] = []

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(lambda _: self._open_selected_excel())

        open_btn = QPushButton("📂 Открыть Excel")
        open_btn.clicked.connect(self._open_selected_excel)

        delete_btn = QPushButton("🗑 Удалить запись")
        delete_btn.clicked.connect(self._delete_selected)

        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.reload)

        button_row = QHBoxLayout()
        button_row.addWidget(open_btn)
        button_row.addWidget(delete_btn)
        button_row.addStretch(1)
        button_row.addWidget(refresh_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(button_row)

        self.reload()

    def reload(self) -> None:
        self._records = self._db_manager.get_all_records()
        self._table.setRowCount(0)
        for record in self._records:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = (record.date, record.supplier, record.source_filename, str(record.items_count), record.excel_path)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col != 2 else Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, col, item)

    def _selected_record(self) -> DocumentRecord | None:
        rows = {index.row() for index in self._table.selectedIndexes()}
        if not rows:
            return None
        row = next(iter(rows))
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def _open_selected_excel(self) -> None:
        record = self._selected_record()
        if record is None:
            QMessageBox.information(self, "История", "Выберите запись в списке.")
            return

        excel_path = Path(record.excel_path)
        if not excel_path.exists():
            QMessageBox.warning(self, "Файл не найден", f"Excel-файл не найден по пути:\n{excel_path}")
            return

        self._open_file_with_system_default(excel_path)

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

    def _delete_selected(self) -> None:
        record = self._selected_record()
        if record is None or record.id is None:
            return

        confirm = QMessageBox.question(
            self,
            "Удаление записи",
            "Удалить эту запись из истории? Excel-файл на диске удален не будет.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._db_manager.delete_record(record.id)
            self.reload()
