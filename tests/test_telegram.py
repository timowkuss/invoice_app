"""Telegram transport is mocked; persistence, authorization and web API are real."""
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from fastapi import HTTPException
from aiogram.filters.command import CommandObject
from test_saas import client, signup, catalog, process
from core.repositories import DocumentRepo, UserRepo
from telegram_bot import bot


def message(chat_id=1001,kind='private',data=None,message_id=1):
    if data is None:
        buffer=io.BytesIO();Image.new('RGB',(50,50),'white').save(buffer,format='PNG');data=buffer.getvalue()
    async def download(path,destination,timeout):
        destination.write(data)
        destination.seek(0)
    transport=SimpleNamespace(get_file=AsyncMock(return_value=SimpleNamespace(file_path='test.png',file_size=len(data))),download_file=AsyncMock(side_effect=download))
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id,type=kind),from_user=SimpleNamespace(id=chat_id),
        bot=transport,message_id=message_id,answer=AsyncMock())


def replies(msg):
    return '\n'.join(call.args[0] for call in msg.answer.call_args_list)


@pytest.fixture
def telegram(client,monkeypatch,tmp_path):
    import core.document_service as service
    monkeypatch.setattr(service,'UPLOAD_DIR',tmp_path/'uploads')
    monkeypatch.setenv('WEB_URL','https://invoice.example.test')
    user,headers=signup(client)
    assert client.post(f'/api/users/{user["id"]}/bind-telegram?chat_id=1001',headers=headers).status_code==200
    return user,headers


def test_telegram_upload_shared_queue_and_web_review(client,telegram,monkeypatch):
    user,h=telegram;catalog(client,h)
    msg=message()
    client.portal.call(bot.process_document,msg,'file-1','invoice.png',100)
    docs=client.get('/api/documents/',headers=h).json()['items']
    assert len(docs)==1
    doc=docs[0]
    assert doc['status']=='retry_pending' and doc['telegram_chat_id']==1001 and doc['telegram_message_id']==1
    assert doc['sent_by_user_id']==user['id']
    assert 'в очереди' in replies(msg)
    keyboard=msg.answer.call_args.kwargs['reply_markup']
    assert keyboard.inline_keyboard[0][0].url==f'https://invoice.example.test/?document={doc["id"]}'
    process(client,h,doc,monkeypatch)
    status=message()
    client.portal.call(bot.cmd_status,status,CommandObject(command='status',args=str(doc['id'])))
    assert 'нужна проверка на сайте' in replies(status)
    assert client.post(f'/api/documents/{doc["id"]}/confirm',headers=h).status_code==200
    assert client.get(f'/api/documents/{doc["id"]}/export',headers=h).status_code==200
    duplicate=message(message_id=2)
    client.portal.call(bot.process_document,duplicate,'same-file','invoice.png',100)
    assert 'Копия не создана' in replies(duplicate)
    assert client.get('/api/documents/',headers=h).json()['total']==1
    assert client.get(f'/api/documents/{doc["id"]}',headers=h).json()['document']['status']=='confirmed'


def test_telegram_rejects_unbound_groups_and_disabled_accounts(client,telegram):
    user,h=telegram
    for msg in (message(9999),message(1001,'group')):
        client.portal.call(bot.process_document,msg,'file','invoice.png',100)
        msg.bot.get_file.assert_not_awaited()
    assert client.put(f'/api/users/{user["id"]}',headers=h,json={'is_active':False}).status_code==409
    async def disable():
        u=await UserRepo.get_by_id(user['id']);u.is_active=False;await UserRepo.update(u)
    client.portal.call(disable)
    msg=message()
    client.portal.call(bot.process_document,msg,'file','invoice.png',100)
    msg.bot.get_file.assert_not_awaited()


def test_telegram_store_isolation_and_unbind(client,telegram):
    _,ha=telegram
    msg=message();client.portal.call(bot.process_document,msg,'file','invoice.png',100)
    doc=client.get('/api/documents/',headers=ha).json()['items'][0]
    b,hb=signup(client,'shop_b')
    assert client.post(f'/api/users/{b["id"]}/bind-telegram?chat_id=1001',headers=hb).status_code==409
    assert client.post(f'/api/users/{b["id"]}/bind-telegram?chat_id=-1',headers=hb).status_code==422
    assert client.post(f'/api/users/{b["id"]}/bind-telegram?chat_id=2002',headers=hb).status_code==200
    other=message(2002)
    client.portal.call(bot.cmd_history,other)
    assert f'#{doc["id"]}' not in replies(other)
    for command in ('status','retry'):
        client.portal.call(bot.cmd_status,other,CommandObject(command=command,args=str(doc['id'])))
    assert 'Накладная не найдена' in replies(other)
    assert client.delete(f'/api/users/{b["id"]}/bind-telegram',headers=ha).status_code==404
    assert client.delete(f'/api/users/{b["id"]}/bind-telegram',headers=hb).status_code==200
    rejected=message(2002);client.portal.call(bot.process_document,rejected,'file','invoice.png',100)
    rejected.bot.get_file.assert_not_awaited()


def test_telegram_limits_failure_and_missing_ocr(client,telegram,monkeypatch):
    _,h=telegram
    for filename,size in [('invoice.exe',100),('invoice.png',bot.MAX_UPLOAD_BYTES+1)]:
        msg=message();client.portal.call(bot.process_document,msg,'file',filename,size);msg.bot.get_file.assert_not_awaited()
    corrupt=message(data=b'not an image')
    client.portal.call(bot.process_document,corrupt,'file','invoice.png',12)
    assert 'Повреждённый' in replies(corrupt)
    assert client.get('/api/documents/',headers=h).json()['total']==0
    failure=message();failure.bot.get_file.side_effect=RuntimeError('SECRET_DOWNLOAD_URL')
    client.portal.call(bot.process_document,failure,'file','invoice.png',10)
    assert 'SECRET_DOWNLOAD_URL' not in replies(failure)
    monkeypatch.delenv('MISTRAL_API_KEY')
    msg=message();client.portal.call(bot.process_document,msg,'file','invoice.png',100)
    assert 'Файл сохранён' in replies(msg)
    docs=client.get('/api/documents/',headers=h).json()['items'];assert docs[0]['status']=='received'
    monkeypatch.setenv('MISTRAL_API_KEY','test-only')
    client.portal.call(bot.cmd_status,msg,CommandObject(command='retry',args=str(docs[0]['id'])))
    assert 'в очереди' in replies(msg)
    monkeypatch.setenv('DAILY_UPLOAD_LIMIT','1')
    data=io.BytesIO();Image.new('RGB',(50,50),'red').save(data,format='PNG')
    msg=message(data=data.getvalue());client.portal.call(bot.process_document,msg,'file2','second.png',100)
    assert 'Достигнут дневной лимит' in replies(msg)
    assert client.get('/api/documents/',headers=h).json()['total']==1


def test_download_buffer_enforces_actual_size(monkeypatch):
    monkeypatch.setattr(bot,'MAX_UPLOAD_BYTES',3)
    with bot.LimitedBuffer() as buffer:
        buffer.write(b'123')
        with pytest.raises(HTTPException):buffer.write(b'4')


def test_telegram_rechecks_access_after_download(client,telegram):
    user,h=telegram
    msg=message()
    original=msg.bot.download_file.side_effect
    async def download_and_unbind(path,destination,timeout):
        await original(path,destination,timeout)
        await UserRepo.set_telegram(user['id'],None)
    msg.bot.download_file.side_effect=download_and_unbind
    client.portal.call(bot.process_document,msg,'file','invoice.png',100)
    assert client.get('/api/documents/',headers=h).json()['total']==0
    assert 'не подключён' in replies(msg)


def test_telegram_disabled_store(client,telegram):
    from core.repositories import StoreRepo
    user,h=telegram
    async def disable_store():
        store=await StoreRepo.get_by_id(user['store_id']);store.is_active=False;await StoreRepo.update(store)
    client.portal.call(disable_store)
    msg=message()
    client.portal.call(bot.process_document,msg,'file','invoice.png',100)
    msg.bot.get_file.assert_not_awaited()
    assert 'Магазин отключён' in replies(msg)
