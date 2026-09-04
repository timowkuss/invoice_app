"""
ui/dialogs/settings_dialog.py

Диалоговое окно настроек приложения: папка экспорта, язык интерфейса,
тема оформления, автооткрытие Excel после создания, движок OCR.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config.config import SUPPORTED_THEMES, SUPPORTED_UI_LANGUAGES
from config.settings import AppSettings, SettingsManager

_LANGUAGE_LABELS = {"ru": "Русский", "en": "English"}
_THEME_LABELS = {"light": "Светлая", "dark": "Тёмная"}
_ENGINE_LABELS = {"mistral": "Mistral OCR (облачный)"}


class SettingsDialog(QDialog):
    """Позволяет пользователю просмотреть и изменить настройки приложения."""

    def __init__(self, settings_manager: SettingsManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚙ Настройки")
        self.setMinimumWidth(480)

        self._settings_manager = settings_manager
        current: AppSettings = settings_manager.settings

        # Папка экспорта
        self._export_folder_edit = QLineEdit(current.export_folder)
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self._browse_export_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._export_folder_edit)
        folder_row.addWidget(browse_btn)

        # Язык интерфейса
        self._language_combo = QComboBox()
        for code in SUPPORTED_UI_LANGUAGES:
            self._language_combo.addItem(_LANGUAGE_LABELS.get(code, code), code)
        self._select_combo_by_data(self._language_combo, current.language)

        # Тема оформления
        self._theme_combo = QComboBox()
        for code in SUPPORTED_THEMES:
            self._theme_combo.addItem(_THEME_LABELS.get(code, code), code)
        self._select_combo_by_data(self._theme_combo, current.theme)

        # Движок OCR
        self._engine_combo = QComboBox()
        self._engine_combo.addItem(_ENGINE_LABELS["mistral"], "mistral")
        self._select_combo_by_data(self._engine_combo, current.ocr_engine)

        # Mistral API ключ
        self._api_key_edit = QLineEdit(current.mistral_api_key)
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-... (получить на console.mistral.ai)")

        # Автооткрытие Excel
        self._auto_open_checkbox = QCheckBox("Автоматически открывать Excel после создания")
        self._auto_open_checkbox.setChecked(current.auto_open_excel)



        form_layout = QFormLayout()
        form_layout.addRow("Папка экспорта:", folder_row)
        form_layout.addRow("Язык интерфейса:", self._language_combo)
        form_layout.addRow("Тема:", self._theme_combo)
        form_layout.addRow("Движок OCR:", self._engine_combo)
        form_layout.addRow("Mistral API ключ:", self._api_key_edit)
        form_layout.addRow("", self._auto_open_checkbox)


        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    @staticmethod
    def _select_combo_by_data(combo: QComboBox, data_value: str) -> None:
        index = combo.findData(data_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _browse_export_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку экспорта", self._export_folder_edit.text())
        if folder:
            self._export_folder_edit.setText(folder)

    def _on_save(self) -> None:
        self._settings_manager.update(
            export_folder=self._export_folder_edit.text().strip(),
            language=self._language_combo.currentData(),
            theme=self._theme_combo.currentData(),
            auto_open_excel=self._auto_open_checkbox.isChecked(),
            ocr_engine=self._engine_combo.currentData(),
            mistral_api_key=self._api_key_edit.text().strip(),

        )
        self.accept()
