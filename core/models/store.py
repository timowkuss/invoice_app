from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Store:
    id: int | None = None
    name: str = ""
    code: str = ""
    address: str = ""
    phone: str = ""
    inn: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "address": self.address,
            "phone": self.phone,
            "inn": self.inn,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> Store:
        return cls(
            id=row.get("id"),
            name=row.get("name", ""),
            code=row.get("code", ""),
            address=row.get("address", ""),
            phone=row.get("phone", ""),
            inn=row.get("inn", ""),
            is_active=row.get("is_active", True),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
