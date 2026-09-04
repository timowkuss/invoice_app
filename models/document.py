"""
models/document.py

Модель записи истории обработанных документов (накладных).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DocumentRecord:
    """Одна запись истории в базе данных."""

    id: int | None = None
    date: str = ""
    supplier: str = ""
    source_filename: str = ""
    items_count: int = 0
    excel_path: str = ""

    @classmethod
    def create_now(
        cls,
        supplier: str,
        source_filename: str,
        items_count: int,
        excel_path: str,
    ) -> "DocumentRecord":
        return cls(
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            supplier=supplier,
            source_filename=source_filename,
            items_count=items_count,
            excel_path=excel_path,
        )
