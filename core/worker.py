"""Persistent document queue. Claims are atomic across server processes."""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from core.database import get_connection, get_transaction
from core.repositories import DocumentRepo, DocumentItemRepo, AiRequestRepo
from core.models.document_item import DocumentItem
from core.models.ai_request import AiRequest
from core.matching.service import MatchingService
from core.ocr_service import recognize, OcrError
from core.uploads import document_path

logger=logging.getLogger(__name__)

def number(value):
    if value is None or not str(value).strip():
        return None
    try:
        result=Decimal(str(value).replace('\u00a0','').replace(' ','').replace(',','.'))
        return result if result.is_finite() and 0<=result<=Decimal('9999999999.99') else None
    except InvalidOperation:
        return None

async def process_claimed(doc):
    started=time.monotonic()
    try:
        products,pages=await recognize(document_path(doc.original_file_url))
        data=[dict(row_number=i,ocr_text=p.name,product_name=p.name,article=p.article,barcode=p.barcode,
                   quantity=p.quantity,price=p.price,total=p.total,unit=p.unit) for i,p in enumerate(products,1)]
        matched=await MatchingService().match_document_items(doc.store_id,data)
        items=[]
        for row in matched:
            row.pop('alternatives',None)
            for field in ('quantity','price','total','confidence'):
                value=row.get(field)
                row[field]=number(value)
            items.append(DocumentItem(document_id=doc.id,**row))
        async with get_transaction():
            await DocumentItemRepo.delete_by_document(doc.id)
            await DocumentItemRepo.bulk_create(items)
            good=sum(item.match_status=='matched' for item in items)
            await DocumentRepo.update_counts(doc.id,len(items),good,len(items)-good)
            await DocumentRepo.update_status(doc.id,'needs_review')
            await AiRequestRepo.create(AiRequest(store_id=doc.store_id,user_id=doc.sent_by_user_id,document_id=doc.id,
                duration_ms=int((time.monotonic()-started)*1000),status='success'))
    except asyncio.CancelledError:
        await DocumentRepo.update_status(doc.id,'error','Обработка прервана обновлением сервера. Повторите вручную.')
        raise
    except Exception as exc:
        # Do not expose provider response bodies, credentials, or filesystem paths.
        message=str(exc) if isinstance(exc,OcrError) else 'Не удалось обработать документ. Попробуйте снова или обратитесь в поддержку.'
        logger.error('Document %s processing failed: %s',doc.id,type(exc).__name__)
        async with get_transaction():
            await DocumentRepo.update_status(doc.id,'error',message)
            await AiRequestRepo.create(AiRequest(store_id=doc.store_id,user_id=doc.sent_by_user_id,document_id=doc.id,
                duration_ms=int((time.monotonic()-started)*1000),status='error',error_message=message))

async def worker_loop():
    while True:
        try:
            async with get_connection() as conn:
                await conn.execute("UPDATE documents SET status='error',error_message='Обработка прервана. Повторите вручную.' WHERE status='processing' AND processed_at<$1",datetime.utcnow()-timedelta(minutes=10))
                doc_id=await conn.fetchval("SELECT id FROM documents WHERE status='retry_pending' ORDER BY created_at,id LIMIT 1")
                claimed=await conn.fetchval("UPDATE documents SET status='processing',processed_at=NOW(),updated_at=NOW() WHERE id=$1 AND status='retry_pending' RETURNING id",doc_id) if doc_id else None
            if claimed:
                await process_claimed(await DocumentRepo.get_by_id(claimed))
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('Queue error: %s',type(exc).__name__)
            await asyncio.sleep(3)
