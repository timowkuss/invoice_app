import os
from fastapi import APIRouter,Depends
from core.database import get_connection
from core.repositories import AiRequestRepo
from api.routers.auth import require_store, require_super_admin
router=APIRouter()

def configured_page_rate():
    try:
        return max(0.0,float(os.getenv('MISTRAL_COST_PER_1000_PAGES_USD','4') or 0))
    except ValueError:
        return 0.0

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

@router.get('/admin-ai-usage')
async def admin_ai_usage(user=Depends(require_super_admin)):
    async with get_connection() as conn:
        summary=await conn.fetchrow(
            """SELECT COUNT(ar.id) AS total_requests,
                      COALESCE(SUM(CASE WHEN ar.status='success' THEN 1 ELSE 0 END),0) AS successful_requests,
                      COALESCE(SUM(CASE WHEN ar.status!='success' THEN 1 ELSE 0 END),0) AS failed_requests,
                      COALESCE(SUM(ar.pages),0) AS total_pages,
                      COALESCE(SUM(ar.total_tokens),0) AS total_tokens,
                      COALESCE(SUM(ar.cost),0) AS total_cost
               FROM ai_requests ar"""
        )
        stores=await conn.fetch(
            """SELECT s.id AS store_id, s.name AS store_name,
                      COUNT(ar.id) AS total_requests,
                      COALESCE(SUM(CASE WHEN ar.status='success' THEN 1 ELSE 0 END),0) AS successful_requests,
                      COALESCE(SUM(CASE WHEN ar.status!='success' THEN 1 ELSE 0 END),0) AS failed_requests,
                      COALESCE(SUM(ar.pages),0) AS total_pages,
                      COALESCE(SUM(ar.total_tokens),0) AS total_tokens,
                      COALESCE(SUM(ar.cost),0) AS total_cost,
                      MAX(ar.created_at) AS last_request_at
               FROM stores s LEFT JOIN ai_requests ar ON ar.store_id=s.id
               GROUP BY s.id,s.name ORDER BY total_requests DESC,s.name"""
        )
        recent=await conn.fetch(
            """SELECT ar.id,ar.store_id,s.name AS store_name,ar.user_id,u.username AS user_email,
                      ar.document_id,ar.model,ar.status,ar.pages,ar.total_tokens,ar.cost,
                      ar.duration_ms,ar.created_at
               FROM ai_requests ar
               LEFT JOIN stores s ON s.id=ar.store_id
               LEFT JOIN users u ON u.id=ar.user_id
               ORDER BY ar.created_at DESC,ar.id DESC LIMIT 50"""
        )
    return {
        'summary':dict(summary),
        'stores':[dict(row) for row in stores],
        'recent':[dict(row) for row in recent],
        'cost_per_1000_pages_usd':configured_page_rate(),
    }
