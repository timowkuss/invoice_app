import os
from fastapi import APIRouter, Depends
from api.routers.auth import require_admin
router = APIRouter()

@router.get('/')
async def settings(user=Depends(require_admin)):
    return {'ocr_configured': bool(os.getenv('MISTRAL_API_KEY')), 'max_upload_mb':20,
            'max_pages':30, 'auto_match_threshold':92,
            'export_note':'Excel содержит код и название из каталога магазина. Формат загрузки настраивается в вашей 1С.'}
