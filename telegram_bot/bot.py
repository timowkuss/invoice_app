"""Telegram intake for the same stores, documents and OCR queue as the web app."""
from __future__ import annotations

import asyncio
import logging
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import HTTPException

from core.config import DATABASE_URL, MAX_UPLOAD_BYTES
from core.database import init_db, close_db
from core.document_service import save_document, queue_document, owned_document
from core.repositories import UserRepo, StoreRepo, DocumentRepo

logger = logging.getLogger(__name__)
dp = Dispatcher()
STATUSES = {
    'received': 'загружена', 'retry_pending': 'в очереди', 'processing': 'распознаётся',
    'recognized': 'распознана', 'matching': 'сопоставление товаров',
    'needs_review': 'нужна проверка на сайте', 'confirmed': 'проверена',
    'sent_to_1c': 'передана в 1С', 'completed': 'завершена', 'error': 'ошибка обработки',
}


class LimitedBuffer(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Файл должен быть не больше 20 МБ')
        return super().write(data)


def document_keyboard(doc_id):
    url = os.getenv('WEB_URL', '').rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Проверить на сайте', url=f'{url}/?document={doc_id}')
    ]])


async def authorized_user(message):
    # Telegram chat IDs are user IDs only in private chats. Never trust group IDs or forwards.
    if message.chat.type != 'private' or not message.from_user or message.from_user.id != message.chat.id:
        raise HTTPException(403, 'Отправьте команду в личный чат с ботом.')
    user = await UserRepo.get_by_telegram(message.from_user.id)
    if not user or not user.store_id:
        raise HTTPException(403, 'Telegram ещё не подключён. Отправьте /id и передайте номер администратору вашего магазина для привязки на сайте.')
    store = await StoreRepo.get_by_id(user.store_id)
    if not store or not store.is_active:
        raise HTTPException(403, 'Магазин отключён. Обратитесь к администратору.')
    return user


def error_text(exc):
    if isinstance(exc, HTTPException) and isinstance(exc.detail, str):
        return exc.detail
    # Telegram exceptions can contain signed download URLs. Never echo/log their contents.
    logger.error('Telegram operation failed: %s', type(exc).__name__)
    return 'Не удалось выполнить запрос. Попробуйте ещё раз. Если файл уже принят, проверьте /history.'


async def send_status(message, doc):
    text = f'Накладная #{doc.id}: {STATUSES.get(doc.status, "обрабатывается")}.\nСтрок: {doc.total_items}; требуют проверки: {doc.needs_review_items}.'
    if doc.status == 'error':
        text += f'\nПовторить распознавание: /retry {doc.id}'
    if doc.status in ('received', 'retry_pending', 'processing'):
        text += f'\nПроверить статус: /status {doc.id}'
    await message.answer(text, reply_markup=document_keyboard(doc.id))


@dp.message(Command('start', 'help'))
async def cmd_start(message: types.Message):
    await message.answer(
        'Отправьте фото или PDF накладной в личный чат. Она появится в вашем магазине на сайте. '
        'После распознавания проверьте товары на сайте и скачайте Excel.\n\n'
        'Первое подключение: /id — передайте номер администратору магазина.\n'
        '/history — последние накладные магазина\n/status НОМЕР — состояние накладной\n'
        '/retry НОМЕР — повторить обработку после ошибки\n'
        'До 20 МБ, PDF до 30 страниц. Один файл — одна накладная; многостраничную отправляйте одним PDF.'
    )


@dp.message(Command('id'))
async def cmd_id(message: types.Message):
    if message.chat.type != 'private' or not message.from_user:
        await message.answer('Отправьте /id в личный чат с ботом.')
        return
    await message.answer(f'Ваш Telegram ID: {message.from_user.id}\nПередайте его администратору магазина: сайт → Команда → Telegram. Пароль от сайта боту не нужен.')


@dp.message(Command('history'))
async def cmd_history(message: types.Message):
    try:
        user = await authorized_user(message)
        docs = await DocumentRepo.list_by_store(user.store_id, limit=5)
        if not docs:
            await message.answer('В вашем магазине пока нет накладных.')
            return
        await message.answer('Последние накладные вашего магазина:\n' + '\n'.join(
            f'#{doc.id} — {STATUSES.get(doc.status, "обрабатывается")} — {doc.total_items} строк' for doc in docs
        ) + '\n\nОткрыть: /status НОМЕР')
    except Exception as exc:
        await message.answer(error_text(exc))


@dp.message(Command('status', 'retry'))
async def cmd_status(message: types.Message, command: CommandObject):
    try:
        user = await authorized_user(message)
        argument = (command.args or '').strip()
        if not argument.isascii() or not argument.isdigit() or not 0 < int(argument) < 2**63:
            raise HTTPException(422, f'Используйте /{command.command} НОМЕР, например /{command.command} 12')
        doc = await owned_document(int(argument), user)
        if command.command == 'retry':
            await queue_document(doc.id, user)
            doc = await owned_document(doc.id, user)
        await send_status(message, doc)
    except Exception as exc:
        await message.answer(error_text(exc))


async def process_document(message, file_id, filename, file_size=None):
    try:
        user = await authorized_user(message)
        if Path(filename).suffix.lower() not in {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}:
            raise HTTPException(415, 'Поддерживаются PDF, JPG, PNG и WebP')
        if file_size and file_size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'Файл должен быть не больше 20 МБ')
        info = await message.bot.get_file(file_id)
        if not info.file_path or (info.file_size and info.file_size > MAX_UPLOAD_BYTES):
            raise HTTPException(413, 'Файл недоступен или превышает 20 МБ')
        with LimitedBuffer() as buffer:
            await message.bot.download_file(info.file_path, destination=buffer, timeout=60)
            data = buffer.getvalue()
        # Recheck binding/active status after the potentially slow network download.
        current = await authorized_user(message)
        if (current.id, current.store_id) != (user.id, user.store_id):
            raise HTTPException(403, 'Привязка аккаунта изменилась. Отправьте файл заново.')
        duplicate = False
        try:
            doc = await save_document(data, filename, current,
                telegram_chat_id=message.chat.id, telegram_message_id=message.message_id)
        except HTTPException as exc:
            if exc.status_code != 409 or not isinstance(exc.detail, dict):
                raise
            doc = await owned_document(exc.detail['document_id'], current)
            duplicate = True
        if not duplicate:
            await message.answer(f'Накладная #{doc.id} сохранена в вашем магазине.')
        else:
            await message.answer(f'Эта накладная уже загружена: #{doc.id}. Копия не создана.')
        if doc.status == 'received':
            try:
                await queue_document(doc.id, current)
            except HTTPException as exc:
                await message.answer(f'Файл сохранён. {error_text(exc)} Повторить: /retry {doc.id}', reply_markup=document_keyboard(doc.id))
                return
        await send_status(message, await owned_document(doc.id, current))
    except Exception as exc:
        await message.answer(error_text(exc))


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    await process_document(message, photo.file_id, f'photo_{message.message_id}.jpg', photo.file_size)


@dp.message(F.document)
async def handle_document(message: types.Message):
    doc = message.document
    await process_document(message, doc.file_id, doc.file_name or '', doc.file_size)


@dp.message()
async def unsupported(message: types.Message):
    await message.answer('Отправьте фото или файл PDF, JPG, PNG, WebP. Справка: /help')


async def main():
    token = os.getenv('TELEGRAM_TOKEN', '')
    if not token or token.startswith('your_'):
        raise RuntimeError('Set TELEGRAM_TOKEN in .env')
    if not document_keyboard(1):
        raise RuntimeError('Set WEB_URL to the public web application URL')
    bot = Bot(token=token)
    try:
        await init_db(DATABASE_URL)
        # OCR is consumed by the web worker, never by the Telegram event loop.
        # Do not discard pending messages or silently replace an existing webhook.
        await dp.start_polling(bot, handle_as_tasks=False, close_bot_session=False)
    finally:
        await bot.session.close()
        await close_db()


if __name__ == '__main__':
    asyncio.run(main())
