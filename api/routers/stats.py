from fastapi import APIRouter,Depends
from core.database import get_connection
from core.repositories import AiRequestRepo
from api.routers.auth import require_store
router=APIRouter()

@router.get('/dashboard')
async def dashboard(user=Depends(require_store)):
    async with get_connection() as conn:
        counts=await conn.fetch('SELECT status,COUNT(*) AS n FROM documents WHERE store_id=$1 GROUP BY status',user.store_id)
        catalog=await conn.fetchval('SELECT COUNT(*) FROM products WHERE store_id=$1 AND is_active=TRUE',user.store_id)
    by_status={row['status']:row['n'] for row in counts}
    return {'documents':sum(by_status.values()),'needs_review':by_status.get('needs_review',0),'confirmed':by_status.get('confirmed',0),'processing':by_status.get('processing',0)+by_status.get('retry_pending',0),'catalog':catalog,'errors':by_status.get('error',0)}

@router.get('/ai-usage')
async def ai_usage(user=Depends(require_store)):
    return {'stats':await AiRequestRepo.stats_by_store(user.store_id),'recent':[r.to_dict() for r in await AiRequestRepo.list_by_store(user.store_id)]}
