from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.models.user import User
from core.repositories import ProductAliasRepo, ProductRepo
from core.matching.service import MatchingService, normalize_text
from api.routers.auth import get_current_user

router = APIRouter()


@router.get("/search")
async def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50),
    user: User = Depends(get_current_user),
):
    products = await ProductRepo.search(user.store_id, q, limit=limit)
    return [p.to_dict() for p in products]


@router.post("/match")
async def match_text(
    text: str,
    user: User = Depends(get_current_user),
):
    matcher = MatchingService()
    result = await matcher.match_product(user.store_id, text)
    return {
        "product": result.product.to_dict() if result.product else None,
        "confidence": result.confidence,
        "method": result.method,
        "alternatives": [p.to_dict() for p in result.alternatives],
    }


@router.get("/aliases")
async def list_aliases(user: User = Depends(get_current_user)):
    aliases = await ProductAliasRepo.list_by_store(user.store_id)
    return [a.to_dict() for a in aliases]


@router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: int, user: User = Depends(get_current_user)):
    deleted = await ProductAliasRepo.delete(alias_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"status": "deleted"}
