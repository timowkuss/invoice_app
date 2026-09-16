"""Create a clearly labelled local demo, never run against production."""
import json
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.config import ROOT,DATABASE_URL
import httpx
from PIL import Image,ImageDraw,ImageFont

if not DATABASE_URL.startswith('sqlite:///'):
    raise SystemExit('Demo is local-only')
folder=ROOT/'.local'
folder.mkdir(exist_ok=True)
credentials=folder/'demo-access.json'
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as client:
    if credentials.exists():
        login=json.loads(credentials.read_text())
        result=client.post('/api/auth/login',json=login)
    else:
        login={'username':'demo','password':secrets.token_urlsafe(18)}
        result=client.post('/api/auth/signup',json={**login,'store_name':'Демо · Магазин у дома'})
        result.raise_for_status()
        credentials.write_text(json.dumps(login),encoding='utf-8')
        (folder/'Доступ.txt').write_text('Локальный сайт: http://localhost:8000\nДемонстрационный магазин\nЛогин: demo\nПароль: '+login['password']+'\n',encoding='utf-8')
    result.raise_for_status()
    catalog='Код 1С;Название;Артикул;Штрихкод;Единица;Цена\n000001;Шадринское Молоко 1л 5%;MILK-5;4600000000001;шт;100\n000002;Шадринское Молоко 1л 3.2%;MILK-32;4600000000002;шт;95\n000003;Хлеб Бородинский 400г;BREAD-400;;шт;60\n'
    (folder/'demo-catalog.csv').write_text(catalog,encoding='utf-8-sig')
    client.post('/api/products/import',files={'file':('catalog.csv',catalog.encode())}).raise_for_status()
    image=Image.new('RGB',(1600,640),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',28)
    title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',36)
    draw.text((40,25),'ТЕСТОВАЯ НАКЛАДНАЯ № 1',fill='black',font=title)
    draw.text((40,85),'Искусственный пример для проверки. Не реальный документ.',fill='black',font=font)
    columns=[40,120,920,1040,1190,1380,1560]
    for x in columns:draw.line((x,170,x,490),fill='black',width=2)
    for y in (170,240,340,440,490):draw.line((40,y,1560,y),fill='black',width=2)
    for x,text in zip(columns,['№','Наименование','Ед.','Кол-во','Цена','Сумма']):draw.text((x+10,190),text,fill='black',font=font)
    for y,row in [(265,['1','Молоко Шадринское 5% 1л','шт','2','100,00','200,00']),(365,['2','Хлеб Бородинский 400г','шт','3','60,00','180,00'])]:
        for x,text in zip(columns,row):draw.text((x+10,y),text,fill='black',font=font)
    draw.text((1080,535),'Итого: 380,00',fill='black',font=title)
    path=folder/'demo-invoice.png'
    image.save(path)
    response=client.post('/api/documents/upload',data={'supplier':'Демо-поставщик (тест)'},files={'file':('demo-invoice.png',path.read_bytes(),'image/png')})
    if response.status_code==409:
        document_id=response.json()['detail']['document_id']
    else:
        response.raise_for_status();document_id=response.json()['id']
    result=client.post(f'/api/documents/{document_id}/process')
    print('Demo document:',document_id,'queue:',result.status_code)
