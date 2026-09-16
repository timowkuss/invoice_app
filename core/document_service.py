"""Shared intake, audit and OCR queue for web and Telegram."""
import asyncio
import hashlib
import os
import uuid
from datetime import datetime,timedelta
from pathlib import Path
from fastapi import HTTPException
from core.config import UPLOAD_DIR,MAX_UPLOAD_BYTES
from core.database import get_transaction
from core.repositories import DocumentRepo,AuditLogRepo
from core.models.document import Document
from core.models.audit_log import AuditLog
from core.uploads import validate_document

async def owned_document(doc_id,user):
    doc=await DocumentRepo.get_by_id(doc_id)
    if not doc or doc.store_id!=user.store_id:
        raise HTTPException(404,'Накладная не найдена')
    return doc

async def lock_document(doc_id,user,conn):
    await conn.execute('UPDATE documents SET updated_at=updated_at WHERE id=$1 AND store_id=$2',doc_id,user.store_id)
    return await owned_document(doc_id,user)

async def audit(user,doc_id,action,old=None,new=None):
    await AuditLogRepo.create(AuditLog(store_id=user.store_id,user_id=user.id,document_id=doc_id,
        action=action,entity_type='document',entity_id=doc_id,old_value=old,new_value=new))

async def save_document(data,filename,user,supplier='',*,upload_dir=None,telegram_chat_id=None,telegram_message_id=None):
    suffix=Path(filename or '').suffix.lower()
    if not data or len(data)>MAX_UPLOAD_BYTES:
        raise HTTPException(413,'Файл пуст или превышает 20 МБ')
    await asyncio.to_thread(validate_document,data,suffix)
    digest=hashlib.sha256(data).hexdigest()
    directory=(upload_dir or UPLOAD_DIR) / str(user.store_id)
    directory.mkdir(parents=True,exist_ok=True)
    path=directory / f'{uuid.uuid4().hex}{suffix}'
    try:
        async with get_transaction() as conn:
            await conn.execute('UPDATE stores SET updated_at=updated_at WHERE id=$1',user.store_id)
            existing=await DocumentRepo.get_by_hash(user.store_id,digest)
            if existing:
                raise HTTPException(409,{'message':'Эта накладная уже загружена','document_id':existing.id})
            daily=await conn.fetchval('SELECT COUNT(*) FROM documents WHERE store_id=$1 AND created_at>=$2',user.store_id,datetime.utcnow()-timedelta(days=1))
            if daily>=int(os.getenv('DAILY_UPLOAD_LIMIT','100')):
                raise HTTPException(429,'Достигнут дневной лимит загрузок магазина')
            await asyncio.to_thread(path.write_bytes,data)
            doc=await DocumentRepo.create(Document(store_id=user.store_id,supplier=supplier,original_file_url=str(path),original_file_hash=digest,sent_by_user_id=user.id,status='received',telegram_chat_id=telegram_chat_id,telegram_message_id=telegram_message_id))
            await audit(user,doc.id,'upload')
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return doc

async def queue_document(doc_id,user):
    if not os.getenv('MISTRAL_API_KEY'):
        raise HTTPException(503,'Mistral ещё не настроен')
    async with get_transaction() as conn:
        doc=await lock_document(doc_id,user,conn)
        if doc.status in ('retry_pending','processing'):
            return {'document_id':doc_id,'status':doc.status}
        if doc.status not in ('received','error'):
            raise HTTPException(409,'Документ уже распознан. Отредактируйте результат.')
        attempts=await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE document_id=$1 AND action='queue_ocr'",doc_id)
        if attempts>=5:
            raise HTTPException(429,'Лимит повторов OCR исчерпан. Обратитесь в поддержку.')
        await DocumentRepo.update_status(doc_id,'retry_pending')
        await audit(user,doc_id,'queue_ocr')
    return {'document_id':doc_id,'status':'retry_pending'}
