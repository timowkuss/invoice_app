"""
json_exporter.py

Сохранение и загрузка черновика накладной в формате JSON.
Промежуточный шаг между OCR и Excel: после распознавания данные
пишутся в JSON, пользователь проверяет/редактирует, затем экспортирует.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from config.config import JSON_DRAFTS_DIR
from models.product import Product
from utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


def _generate_draft_path(drafts_dir: Path, source_name: str = "") -> Path:
    """Формирует путь к JSON-черновику: json_drafts/DD-MM-YYYY_HH-MM-SS[_source].json"""
    ensure_dir(drafts_dir)
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    suffix = f"_{Path(source_name).stem}" if source_name else ""
    return drafts_dir / f"{timestamp}{suffix}.json"


def save_draft(
    products: list[Product],
    source_filename: str = "",
    output_path: Path | None = None,
    drafts_dir: Path | None = None,
) -> Path:
    """
    Сохраняет список товаров в JSON-файл.

    Args:
        products: Список распознанных товаров.
        source_filename: Имя исходного файла (накладной) для мета-инфы.
        output_path: Конкретный путь для сохранения (если None — генерируется автоматически).
        drafts_dir: Директория для черновиков (по умолчанию JSON_DRAFTS_DIR).

    Returns:
        Путь к сохранённому JSON-файлу.
    """
    directory = drafts_dir or JSON_DRAFTS_DIR
    if output_path is None:
        output_path = _generate_draft_path(directory, source_filename)

    ensure_dir(output_path.parent)

    draft = {
        "source": source_filename,
        "created_at": datetime.now().isoformat(),
        "items_count": len(products),
        "products": [p.to_dict() for p in products],
    }

    output_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("JSON-черновик сохранён: %s (%d товаров)", output_path, len(products))
    return output_path


def load_draft(json_path: Path | str) -> list[Product]:
    """
    Загружает список товаров из JSON-файла.

    Args:
        json_path: Путь к JSON-файлу черновика.

    Returns:
        Список объектов Product.

    Raises:
        FileNotFoundError: Файл не найден.
        json.JSONDecodeError: Некорректный JSON.
        KeyError: Отсутствует ключ 'products'.
    """
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    products = [Product.from_dict(item) for item in data["products"]]
    logger.info("JSON-черновик загружен: %s (%d товаров)", path, len(products))
    return products


def get_draft_metadata(json_path: Path | str) -> dict:
    """Возвращает мета-данные черновика (без загрузки всех товаров)."""
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "source": data.get("source", ""),
        "created_at": data.get("created_at", ""),
        "items_count": data.get("items_count", 0),
    }
