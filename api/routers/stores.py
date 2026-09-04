from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.models.user import User
from core.repositories import StoreRepo
from api.routers.auth import get_current_user, require_super_admin

router = APIRouter()


class StoreCreate(BaseModel):
    name: str
    code: str
    address: str = ""
    phone: str = ""
    inn: str = ""


@router.get("/")
async def list_stores(user: User = Depends(get_current_user)):
    if user.is_super_admin:
        stores = await StoreRepo.list_all()
    else:
        from core.database import get_connection
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM stores WHERE id = $1", user.store_id)
            stores = [row] if row else []
    return [s if isinstance(s, dict) else s.to_dict() for s in stores]


@router.post("/")
async def create_store(req: StoreCreate, user: User = Depends(require_super_admin)):
    from core.models.store import Store
    store = Store(name=req.name, code=req.code, address=req.address, phone=req.phone, inn=req.inn)
    return (await StoreRepo.create(store)).to_dict()


@router.get("/{store_id}")
async def get_store(store_id: int, user: User = Depends(get_current_user)):
    if not user.is_super_admin and user.store_id != store_id:
        raise HTTPException(status_code=403, detail="Access denied")
    store = await StoreRepo.get_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store.to_dict()
