"""
utils/file_utils.py

Вспомогательные функции для работы с файлами: генерация
уникальных имен, проверка расширений, создание директорий.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config.config import ALL_SUPPORTED_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_PDF_EXTENSIONS


def ensure_dir(path: Path) -> Path:
    """Создает директорию (и родительские), если она не существует."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in ALL_SUPPORTED_EXTENSIONS


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_pdf_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_PDF_EXTENSIONS


def generate_export_filename(extension: str = "xlsx") -> str:
    """Формирует имя файла вида 'Дата_Время.xlsx'."""
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    return f"{timestamp}.{extension.lstrip('.')}"


def generate_export_path(export_folder: Path) -> Path:
    ensure_dir(export_folder)
    return export_folder / generate_export_filename("xlsx")
