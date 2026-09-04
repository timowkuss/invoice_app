from __future__ import annotations

from datetime import datetime, date
from dataclasses import dataclass, field


@dataclass
class Document:
    id: int | None = None
    store_id: int | None = None
    supplier: str = ""
    document_number: str = ""
    document_date: date | None = None
    status: str = "received"
    original_file_url: str = ""
    original_file_hash: str = ""
    telegram_message_id: int | None = None
    telegram_chat_id: int | None = None
    sent_by_user_id: int | None = None
    total_items: int = 0
    matched_items: int = 0
    needs_review_items: int = 0
    error_message: str = ""
    processed_at: datetime | None = None
    confirmed_at: datetime | None = None
    sent_to_1c_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    STATUSES = (
        "received", "processing", "recognized", "matching",
        "needs_review", "confirmed", "sent_to_1c", "completed", "error",
        "retry_pending",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "supplier": self.supplier,
            "document_number": self.document_number,
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "status": self.status,
            "original_file_url": self.original_file_url,
            "original_file_hash": self.original_file_hash,
            "telegram_message_id": self.telegram_message_id,
            "telegram_chat_id": self.telegram_chat_id,
            "sent_by_user_id": self.sent_by_user_id,
            "total_items": self.total_items,
            "matched_items": self.matched_items,
            "needs_review_items": self.needs_review_items,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "sent_to_1c_at": self.sent_to_1c_at.isoformat() if self.sent_to_1c_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> Document:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            supplier=row.get("supplier", ""),
            document_number=row.get("document_number", ""),
            document_date=row.get("document_date"),
            status=row.get("status", "received"),
            original_file_url=row.get("original_file_url", ""),
            original_file_hash=row.get("original_file_hash", ""),
            telegram_message_id=row.get("telegram_message_id"),
            telegram_chat_id=row.get("telegram_chat_id"),
            sent_by_user_id=row.get("sent_by_user_id"),
            total_items=row.get("total_items", 0),
            matched_items=row.get("matched_items", 0),
            needs_review_items=row.get("needs_review_items", 0),
            error_message=row.get("error_message", ""),
            processed_at=row.get("processed_at"),
            confirmed_at=row.get("confirmed_at"),
            sent_to_1c_at=row.get("sent_to_1c_at"),
            completed_at=row.get("completed_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
