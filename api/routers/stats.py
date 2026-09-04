from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from core.models.user import User
from core.repositories import DocumentRepo, AiRequestRepo
from core.database import get_connection
from api.routers.auth import get_current_user

router = APIRouter()


@router.get("/dashboard")
async def dashboard(
    period: str = Query("today"),
    user: User = Depends(get_current_user),
):
    store_id = user.store_id

    if period == "today":
        date_from = datetime.now().strftime("%Y-%m-%d")
    elif period == "7days":
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "30days":
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "month":
        date_from = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    else:
        date_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    async with get_connection() as conn:
        today = datetime.now().strftime("%Y-%m-%d")

        today_count = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND created_at >= $2",
            store_id, today,
        )

        period_count = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND created_at >= $2",
            store_id, date_from,
        )

        needs_review = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND status = 'needs_review'",
            store_id,
        )

        sent_to_1c = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND status IN ('sent_to_1c', 'completed')",
            store_id,
        )

        errors = await conn.fetchval(
            "SELECT COUNT(*) FROM documents WHERE store_id = $1 AND status = 'error'",
            store_id,
        )

        ai_stats = await AiRequestRepo.stats_by_store(store_id, date_from=date_from)

    return {
        "today_count": today_count,
        "period_count": period_count,
        "needs_review": needs_review,
        "sent_to_1c": sent_to_1c,
        "errors": errors,
        "ai_requests": ai_stats.get("total_requests", 0),
        "ai_tokens": ai_stats.get("total_tokens", 0),
        "ai_cost": float(ai_stats.get("total_cost", 0)),
    }


@router.get("/ai-usage")
async def ai_usage(
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user),
):
    stats = await AiRequestRepo.stats_by_store(user.store_id, date_from=date_from, date_to=date_to)
    requests = await AiRequestRepo.list_by_store(user.store_id, limit=50)
    return {
        "stats": stats,
        "recent": [r.to_dict() for r in requests],
    }
