"""
config/config.py

Глобальные константы приложения: пути, поддерживаемые форматы,
значения по умолчанию. Все пути строятся относительно корня проекта,
поэтому приложение можно переносить в любую папку.
"""

from __future__ import annotations

from pathlib import Path

# Корень проекта (папка, где лежит main.py)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Основные директории
LOGS_DIR: Path = BASE_DIR / "logs"
EXPORTS_DIR: Path = BASE_DIR / "exports"
TEMP_DIR: Path = BASE_DIR / "temp"
CONFIG_DIR: Path = BASE_DIR / "config"
DATABASE_DIR: Path = BASE_DIR / "database"
JSON_DRAFTS_DIR: Path = BASE_DIR / "json_drafts"

# Файлы
LOG_FILE: Path = LOGS_DIR / "app.log"
SETTINGS_FILE: Path = CONFIG_DIR / "settings.json"
DATABASE_FILE: Path = DATABASE_DIR / "history.db"

# Поддерживаемые форматы файлов
SUPPORTED_IMAGE_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp")
SUPPORTED_PDF_EXTENSIONS: tuple[str, ...] = (".pdf",)
ALL_SUPPORTED_EXTENSIONS: tuple[str, ...] = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_PDF_EXTENSIONS

# Колонки итоговой таблицы (порядок важен для экспорта в Excel / отображения)
TABLE_COLUMNS: tuple[str, ...] = (
    "Название",
    "Артикул",
    "Штрихкод",
    "Количество",
    "Цена",
    "Сумма",
    "Единица",
)

# Значения настроек по умолчанию
DEFAULT_SETTINGS: dict = {
    "export_folder": str(EXPORTS_DIR),
    "language": "ru",
    "theme": "light",
    "auto_open_excel": True,
    "ocr_languages": ["ru", "en"],
    "ocr_gpu": False,
    "mistral_api_key": "",
    "ocr_engine": "mistral",
}

# Поддерживаемые языки интерфейса
SUPPORTED_UI_LANGUAGES: tuple[str, ...] = ("ru", "en")

# Поддерживаемые темы
SUPPORTED_THEMES: tuple[str, ...] = ("light", "dark")

APP_NAME = "Invoice Recognizer"
APP_VERSION = "1.0.0"
