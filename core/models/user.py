from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class User:
    id: int | None = None
    store_id: int | None = None
    username: str = ""
    password_hash: str = ""
    full_name: str = ""
    role: str = "operator"  # super_admin, store_admin, operator
    telegram_chat_id: int | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "telegram_chat_id": self.telegram_chat_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> User:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            username=row.get("username", ""),
            password_hash=row.get("password_hash", ""),
            full_name=row.get("full_name", ""),
            role=row.get("role", "operator"),
            telegram_chat_id=row.get("telegram_chat_id"),
            is_active=row.get("is_active", True),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def is_store_admin(self) -> bool:
        return self.role in ("super_admin", "store_admin")

    @property
    def is_operator(self) -> bool:
        return self.role in ("super_admin", "store_admin", "operator")
