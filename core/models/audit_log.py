from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class AuditLog:
    id: int | None = None
    store_id: int | None = None
    user_id: int | None = None
    document_id: int | None = None
    action: str = ""
    entity_type: str = ""
    entity_id: int | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    ip_address: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> AuditLog:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            user_id=row.get("user_id"),
            document_id=row.get("document_id"),
            action=row.get("action", ""),
            entity_type=row.get("entity_type", ""),
            entity_id=row.get("entity_id"),
            old_value=row.get("old_value"),
            new_value=row.get("new_value"),
            ip_address=row.get("ip_address", ""),
            created_at=row.get("created_at"),
        )
