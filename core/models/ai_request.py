from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class AiRequest:
    id: int | None = None
    store_id: int | None = None
    user_id: int | None = None
    document_id: int | None = None
    provider: str = "mistral"
    model: str = "mistral-ocr-latest"
    request_type: str = "ocr"  # ocr, matching, other
    status: str = "success"  # success, error, timeout
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    error_message: str = ""
    duration_ms: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "store_id": self.store_id,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "provider": self.provider,
            "model": self.model,
            "request_type": self.request_type,
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> AiRequest:
        return cls(
            id=row.get("id"),
            store_id=row.get("store_id"),
            user_id=row.get("user_id"),
            document_id=row.get("document_id"),
            provider=row.get("provider", "mistral"),
            model=row.get("model", "mistral-ocr-latest"),
            request_type=row.get("request_type", "ocr"),
            status=row.get("status", "success"),
            input_tokens=row.get("input_tokens", 0),
            output_tokens=row.get("output_tokens", 0),
            total_tokens=row.get("total_tokens", 0),
            cost=row.get("cost", 0.0),
            error_message=row.get("error_message", ""),
            duration_ms=row.get("duration_ms", 0),
            created_at=row.get("created_at"),
        )
