from pathlib import Path
from io import BytesIO
from fastapi import HTTPException, UploadFile
from PIL import Image
from pypdf import PdfReader
from core.config import MAX_UPLOAD_BYTES, MAX_PAGES, UPLOAD_DIR

async def read_upload(file: UploadFile, limit=MAX_UPLOAD_BYTES):
    data=bytearray()
    while chunk := await file.read(1024*1024):
        data.extend(chunk)
        if len(data)>limit:
            raise HTTPException(413, f'Файл должен быть меньше {limit//1024//1024} МБ')
    if not data:
        raise HTTPException(422, 'Файл пуст')
    return bytes(data)

def validate_document(data, suffix):
    if suffix not in {'.pdf','.jpg','.jpeg','.png','.webp'}:
        raise HTTPException(415, 'Поддерживаются PDF, JPG, PNG и WebP')
    try:
        if suffix=='.pdf':
            if not data.startswith(b'%PDF-'):
                raise ValueError()
            pdf=PdfReader(BytesIO(data))
            if pdf.is_encrypted or not 1<=len(pdf.pages)<=MAX_PAGES:
                raise ValueError()
        else:
            with Image.open(BytesIO(data)) as img:
                if img.format not in {'JPEG','PNG','WEBP'} or img.width*img.height>40_000_000:
                    raise ValueError()
                expected={'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.webp':'WEBP'}[suffix]
                if img.format != expected:
                    raise ValueError()
                img.verify()
    except Exception:
        raise HTTPException(422, 'Повреждённый файл, неверное расширение или превышен лимит: 30 страниц / 40 Мп') from None

def document_path(value):
    path=Path(value).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, 'Исходный файл не найден')
    return path
