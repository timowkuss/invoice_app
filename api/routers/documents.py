from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from core.models.user import User
from core.models.document import Document
from core.models.document_item import DocumentItem
from core.repositories import DocumentRepo, DocumentItemRepo, AuditLogRepo, AiRequestRepo
from core.models.audit_log import AuditLog
from core.models.ai_request import AiRequest
from api.routers.auth import get_current_user, require_admin
from ocr.pipeline import OcrPipeline

router = APIRouter()

UPLOAD_DIR = "uploads"


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    supplier: str = Form(""),
    user: User = Depends(get_current_user),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    existing = await DocumentRepo.get_by_hash(user.store_id, file_hash)
    if existing:
        raise HTTPException(status_code=409, detail="Document already uploaded")

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    doc = Document(
        store_id=user.store_id,
        supplier=supplier,
        original_file_url=filepath,
        original_file_hash=file_hash,
        sent_by_user_id=user.id,
        status="received",
    )
    doc = await DocumentRepo.create(doc)

    await AuditLogRepo.create(AuditLog(
        store_id=user.store_id,
        user_id=user.id,
        document_id=doc.id,
        action="upload",
        entity_type="document",
        entity_id=doc.id,
    ))

    return doc.to_dict()


@router.post("/{doc_id}/process")
async def process_document(
    doc_id: int,
    user: User = Depends(get_current_user),
):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    await DocumentRepo.update_status(doc_id, "processing")

    from core.database import get_connection
    settings_row = await (await get_connection()).fetchrow(
        "SELECT value FROM app_settings WHERE key = 'mistral_api_key'"
    )
    mistral_key = ""
    if settings_row:
        mistral_key = str(settings_row["value"])

    if not mistral_key:
        from config.settings import SettingsManager
        sm = SettingsManager()
        mistral_key = sm.settings.mistral_api_key

    pipeline = OcrPipeline(mistral_api_key=mistral_key)

    try:
        result = pipeline.process_file(doc.original_file_url)
        await DocumentRepo.update_status(doc_id, "recognized")
    except Exception as e:
        await DocumentRepo.update_status(doc_id, "error", str(e))
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")

    from core.matching.service import MatchingService
    matcher = MatchingService()

    items_data = []
    for i, product in enumerate(result.products, 1):
        items_data.append({
            "row_number": i,
            "product_name": product.name,
            "article": product.article,
            "barcode": product.barcode,
            "quantity": product.quantity,
            "price": product.price,
            "total": product.total,
            "unit": product.unit,
            "ocr_text": product.name,
        })

    matched_items = await matcher.match_document_items(user.store_id, items_data)

    doc_items = []
    total = len(matched_items)
    matched_count = 0
    needs_review_count = 0

    for item_data in matched_items:
        di = DocumentItem(
            document_id=doc_id,
            product_id=item_data.get("product_id"),
            row_number=item_data["row_number"],
            ocr_text=item_data.get("ocr_text", ""),
            product_name=item_data.get("product_name", ""),
            article=item_data.get("article", ""),
            barcode=item_data.get("barcode", ""),
            quantity=item_data.get("quantity"),
            price=item_data.get("price"),
            total=item_data.get("total"),
            unit=item_data.get("unit", ""),
            confidence=item_data.get("confidence"),
            match_status=item_data.get("match_status", "pending"),
        )
        doc_items.append(di)
        if di.match_status == "matched":
            matched_count += 1
        elif di.match_status == "needs_review":
            needs_review_count += 1

    await DocumentItemRepo.bulk_create(doc_items)
    await DocumentRepo.update_counts(doc_id, total, matched_count, needs_review_count)

    final_status = "needs_review" if needs_review_count > 0 else "recognized"
    await DocumentRepo.update_status(doc_id, final_status)

    await AuditLogRepo.create(AuditLog(
        store_id=user.store_id,
        user_id=user.id,
        document_id=doc_id,
        action="process",
        entity_type="document",
        entity_id=doc_id,
        new_value={"total": total, "matched": matched_count, "needs_review": needs_review_count},
    ))

    return {
        "document_id": doc_id,
        "status": final_status,
        "total_items": total,
        "matched_items": matched_count,
        "needs_review_items": needs_review_count,
    }


@router.get("/")
async def list_documents(
    status: str | None = None,
    supplier: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
):
    docs = await DocumentRepo.list_by_store(
        user.store_id, status=status, supplier=supplier,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    total = await DocumentRepo.count_by_store(user.store_id, status=status)
    return {"items": [d.to_dict() for d in docs], "total": total}


@router.get("/{doc_id}")
async def get_document(doc_id: int, user: User = Depends(get_current_user)):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    items = await DocumentItemRepo.list_by_document(doc_id)
    return {
        "document": doc.to_dict(),
        "items": [i.to_dict() for i in items],
    }


@router.get("/{doc_id}/image")
async def get_document_image(doc_id: int, user: User = Depends(get_current_user)):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    if not doc.original_file_url or not os.path.exists(doc.original_file_url):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(doc.original_file_url)


@router.put("/{doc_id}/items/{item_id}")
async def update_document_item(
    doc_id: int,
    item_id: int,
    product_id: int | None = None,
    quantity: float | None = None,
    price: float | None = None,
    create_alias: bool = False,
    user: User = Depends(get_current_user),
):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    item = await DocumentItemRepo.get_by_id(item_id)
    if not item or item.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Item not found")

    old_value = item.to_dict()

    if product_id is not None:
        item.product_id = product_id
        from core.repositories import ProductRepo
        product = await ProductRepo.get_by_id(product_id)
        if product:
            item.product_name = product.name
            item.article = product.article
            item.barcode = product.barcode
            item.unit = product.unit
        item.match_status = "manual"
    if quantity is not None:
        item.quantity = quantity
    if price is not None:
        item.price = price
    if item.quantity and item.price:
        item.total = item.quantity * item.price

    item = await DocumentItemRepo.update(item)

    if create_alias and item.ocr_text and product_id:
        from core.matching.service import normalize_text
        from core.repositories import ProductAliasRepo
        from core.models.product_alias import ProductAlias
        alias = ProductAlias(
            store_id=user.store_id,
            product_id=product_id,
            ocr_text=item.ocr_text,
            normalized_text=normalize_text(item.ocr_text),
            confidence=100.0,
            created_by=user.id,
        )
        await ProductAliasRepo.create(alias)

    await AuditLogRepo.create(AuditLog(
        store_id=user.store_id,
        user_id=user.id,
        document_id=doc_id,
        action="update_item",
        entity_type="document_item",
        entity_id=item_id,
        old_value=old_value,
        new_value=item.to_dict(),
    ))

    return item.to_dict()


@router.post("/{doc_id}/confirm")
async def confirm_document(doc_id: int, user: User = Depends(get_current_user)):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    await DocumentRepo.update_status(doc_id, "confirmed")
    await AuditLogRepo.create(AuditLog(
        store_id=user.store_id,
        user_id=user.id,
        document_id=doc_id,
        action="confirm",
        entity_type="document",
        entity_id=doc_id,
    ))
    return {"status": "confirmed"}


@router.post("/{doc_id}/retry")
async def retry_document(doc_id: int, user: User = Depends(get_current_user)):
    doc = await DocumentRepo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.store_id != user.store_id and not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    await DocumentRepo.update_status(doc_id, "retry_pending")
    return {"status": "retry_pending"}


@router.get("/{doc_id}/audit")
async def get_document_audit(doc_id: int, user: User = Depends(get_current_user)):
    logs = await AuditLogRepo.list_by_document(doc_id)
    return [l.to_dict() for l in logs]
