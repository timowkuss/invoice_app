from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal

from core.models.user import User
from core.repositories import UserRepo
from api.routers.auth import get_current_user, require_admin

router = APIRouter()


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Literal['operator', 'store_admin', 'super_admin'] | None = None
    store_id: int | None = None
    is_active: bool | None = None


@router.get("/")
async def list_users(user: User = Depends(require_admin)):
    if user.is_super_admin:
        users = await UserRepo.list_all()
    else:
        users = await UserRepo.list_by_store(user.store_id)
    return [u.to_dict() for u in users]


@router.get("/{user_id}")
async def get_user(user_id: int, user: User = Depends(require_admin)):
    target = await UserRepo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_super_admin and target.store_id != user.store_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return target.to_dict()


@router.put("/{user_id}")
async def update_user(user_id: int, req: UserUpdate, user: User = Depends(require_admin)):
    target = await UserRepo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_super_admin and target.store_id != user.store_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not user.is_super_admin and (target.is_super_admin or req.role == 'super_admin' or req.store_id not in (None, user.store_id)):
        raise HTTPException(403, 'Нельзя изменить эти права или магазин')
    if target.id == user.id and (req.is_active is False or req.role not in (None, user.role)):
        raise HTTPException(409, 'Нельзя отключить себя или снять собственные права')
    if req.store_id is not None:
        from core.repositories import StoreRepo
        if not await StoreRepo.get_by_id(req.store_id):
            raise HTTPException(404, 'Магазин не найден')
    if req.full_name is not None:
        target.full_name = req.full_name
    if req.role is not None:
        target.role = req.role
    if req.store_id is not None:
        target.store_id = req.store_id
    if req.is_active is not None:
        target.is_active = req.is_active

    return (await UserRepo.update(target)).to_dict()


@router.post("/{user_id}/bind-telegram")
async def bind_telegram(user_id: int, chat_id: int, user: User = Depends(require_admin)):
    target = await UserRepo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_super_admin and (target.store_id != user.store_id or target.is_super_admin):
        raise HTTPException(404, 'Пользователь не найден')
    await UserRepo.set_telegram(user_id, chat_id)
    return {"status": "ok"}
