from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.models.user import User
from core.database import get_connection
from api.routers.auth import get_current_user, require_admin

router = APIRouter()


class SettingUpdate(BaseModel):
    key: str
    value: str | int | float | bool


@router.get("/")
async def get_settings(user: User = Depends(require_admin)):
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT key, value, description FROM app_settings ORDER BY key")
        return {r["key"]: {"value": r["value"], "description": r["description"]} for r in rows}


@router.put("/")
async def update_setting(req: SettingUpdate, user: User = Depends(require_admin)):
    async with get_connection() as conn:
        import json
        await conn.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()""",
            req.key, json.dumps(req.value),
        )
    return {"status": "ok", "key": req.key, "value": req.value}
