from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.models.user import User
from core.repositories import ProductRepo, ProductAliasRepo
from api.routers.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_products(
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    user: User = Depends(get_current_user),
):
    if search:
        products = await ProductRepo.search(user.store_id, search, limit=limit)
    else:
        products = await ProductRepo.list_by_store(user.store_id, limit=limit, offset=offset)
    total = await ProductRepo.count_by_store(user.store_id)
    return {"items": [p.to_dict() for p in products], "total": total}


@router.get("/{product_id}")
async def get_product(product_id: int, user: User = Depends(get_current_user)):
    product = await ProductRepo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    aliases = await ProductAliasRepo.list_by_product(product_id)
    return {
        "product": product.to_dict(),
        "aliases": [a.to_dict() for a in aliases],
    }


@router.get("/{product_id}/aliases")
async def get_product_aliases(product_id: int, user: User = Depends(get_current_user)):
    aliases = await ProductAliasRepo.list_by_product(product_id)
    return [a.to_dict() for a in aliases]
