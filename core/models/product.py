from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Product:
    id: int | None = None
    store_id: int | None = None
    one_c_id: str = ""
    name: str = ""
    article: str = ""
    barcode: str = ""
    unit: str = ""
    weight: float | None = None
    volume: float | None = None
    fat_content: float | None = None
    category: str = ""
    price: float | None = None
    is_active: bool = True
    synced_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "one_c_id": self.one_c_id,
            "name": self.name,
            "article": self.article,
            "barcode": self.barcode,
            "unit": self.unit,
            "weight": self.weight,
            "volume": self.volume,
            "fat_content": self.fat_content,
            "category": self.category,
            "price": self.price,
            "is_active": self.is_active,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> Product:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            one_c_id=row.get("one_c_id", ""),
            name=row.get("name", ""),
            article=row.get("article", ""),
            barcode=row.get("barcode", ""),
            unit=row.get("unit", ""),
            weight=row.get("weight"),
            volume=row.get("volume"),
            fat_content=row.get("fat_content"),
            category=row.get("category", ""),
            price=row.get("price"),
            is_active=row.get("is_active", True),
            synced_at=row.get("synced_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
