from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class DocumentItem:
    id: int | None = None
    document_id: int | None = None
    product_id: int | None = None
    row_number: int = 0
    ocr_text: str = ""
    product_name: str = ""
    article: str = ""
    barcode: str = ""
    quantity: float | None = None
    price: float | None = None
    total: float | None = None
    unit: str = ""
    confidence: float | None = None
    match_status: str = "pending"  # pending, matched, manual, not_found
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "product_id": self.product_id,
            "row_number": self.row_number,
            "ocr_text": self.ocr_text,
            "product_name": self.product_name,
            "article": self.article,
            "barcode": self.barcode,
            "quantity": self.quantity,
            "price": self.price,
            "total": self.total,
            "unit": self.unit,
            "confidence": self.confidence,
            "match_status": self.match_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> DocumentItem:
        return cls(
            id=row.get("id"),
            document_id=row.get("document_id"),
            product_id=row.get("product_id"),
            row_number=row.get("row_number", 0),
            ocr_text=row.get("ocr_text", ""),
            product_name=row.get("product_name", ""),
            article=row.get("article", ""),
            barcode=row.get("barcode", ""),
            quantity=row.get("quantity"),
            price=row.get("price"),
            total=row.get("total"),
            unit=row.get("unit", ""),
            confidence=row.get("confidence"),
            match_status=row.get("match_status", "pending"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
