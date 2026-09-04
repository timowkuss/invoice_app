from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ProductAlias:
    id: int | None = None
    store_id: int | None = None
    product_id: int | None = None
    ocr_text: str = ""
    normalized_text: str = ""
    confidence: float = 100.0
    usage_count: int = 0
    created_by: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "product_id": self.product_id,
            "ocr_text": self.ocr_text,
            "normalized_text": self.normalized_text,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> ProductAlias:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            product_id=row.get("product_id"),
            ocr_text=row.get("ocr_text", ""),
            normalized_text=row.get("normalized_text", ""),
            confidence=row.get("confidence", 100.0),
            usage_count=row.get("usage_count", 0),
            created_by=row.get("created_by"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
