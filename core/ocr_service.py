import base64
import os
import re
from pathlib import Path
import httpx
from ocr.mistral_parser import parse_ocr_result

class OcrError(Exception):
    pass

async def recognize(path: Path):
    key = os.getenv('MISTRAL_API_KEY', '')
    if not key:
        raise OcrError('Mistral не настроен. Обратитесь к владельцу сервиса.')
    kind = 'document_url' if path.suffix.lower()=='.pdf' else 'image_url'
    mime = {'.pdf':'application/pdf','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}[path.suffix.lower()]
    data = base64.b64encode(path.read_bytes()).decode('ascii')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as client:
            response = await client.post('https://api.mistral.ai/v1/ocr', headers={'Authorization':f'Bearer {key}'}, json={
                'model':os.getenv('MISTRAL_OCR_MODEL','mistral-ocr-latest'),
                'document':{'type':kind,kind:f'data:{mime};base64,{data}'},
                'table_format':'html','include_image_base64':False,
            })
        if response.status_code in (401,403):
            raise OcrError('Mistral отклонил API-ключ. Обратитесь к владельцу сервиса.')
        if response.status_code==429:
            raise OcrError('Лимит Mistral исчерпан. Повторите позже.')
        if response.is_error:
            raise OcrError(f'Mistral временно недоступен (HTTP {response.status_code}).')
        payload=response.json()
    except httpx.TimeoutException:
        raise OcrError('Mistral не ответил вовремя. Проверьте результат перед повторным запуском.') from None
    except (httpx.HTTPError, ValueError):
        raise OcrError('Не удалось получить ответ Mistral.') from None
    sections=[]
    for page in payload.get('pages',[]):
        markdown=page.get('markdown','')
        for table in page.get('tables') or []:
            content=table.get('content','')
            table_id=table.get('id','')
            pattern=r'!?\[[^\]]*\]\('+re.escape(table_id)+r'\)'
            if table_id and re.search(pattern, markdown):
                markdown=re.sub(pattern, lambda _:content, markdown)
            elif content and content not in markdown:
                markdown+='\n'+content
        sections.append(markdown)
    products=parse_ocr_result('\n\n'.join(sections))
    if not products:
        raise OcrError('Не найдены строки товаров. Загрузите более чёткое фото или скан таблицы.')
    if len(products)>2000:
        raise OcrError('В документе больше 2000 строк. Разделите накладную.')
    return products, len(payload.get('pages',[]))
