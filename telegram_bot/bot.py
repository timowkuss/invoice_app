from __future__ import annotations

import os
import sys
import hashlib
import logging
import sqlite3
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import DATABASE_FILE, TEMP_DIR
from models.product import Product
from models.document import DocumentRecord
from database.db_manager import DatabaseManager
from ocr.pipeline import OcrPipeline
from excel.exporter import ExcelExporter

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
WEB_URL = os.getenv("WEB_URL", "http://localhost:8000")

bot: Bot = None  # type: ignore
dp = Dispatcher()

db = DatabaseManager(DATABASE_FILE)


def _get_bot() -> Bot:
    global bot
    if bot is None:
        if not TELEGRAM_TOKEN:
            raise RuntimeError("TELEGRAM_TOKEN not set in environment")
        bot = Bot(token=TELEGRAM_TOKEN)
    return bot


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для обработки накладных.\n\n"
        "Отправьте мне фотографию или PDF накладной, и я её обработаю.\n\n"
        "Команды:\n"
        "/start - Приветствие\n"
        "/history - Последние документы\n"
        "/help - Помощь"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Отправьте фотографию или PDF накладной\n"
        "2. Бот распознает документ через Mistral OCR\n"
        "3. Результат сохранится и будет доступен для экспорта\n\n"
        "Команды:\n"
        "/start - Приветствие\n"
        "/history - Последние документы\n"
        "/help - Помощь"
    )


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    records = db.get_all_records()
    if not records:
        await message.answer("Пока нет документов.")
        return

    lines = ["Последние документы:\n"]
    for r in records[:5]:
        lines.append(f"#{r.id} | {r.date} | {r.supplier or '-'} | {r.items_count} шт.")
    await message.answer("\n".join(lines))


async def process_document(message: types.Message, file_id: str, filename: str):
    status_msg = await message.answer("Скачиваю файл...")

    b = _get_bot()
    file_info = await b.get_file(file_id)
    file_bytes = await b.download_file(file_info.file_path)
    content = file_bytes.read()

    os.makedirs(TEMP_DIR, exist_ok=True)
    ext = os.path.splitext(filename)[1] or ".jpg"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = str(TEMP_DIR / saved_name)
    with open(saved_path, "wb") as f:
        f.write(content)

    await status_msg.edit_text("Распознаю документ через Mistral OCR...")

    pipeline = OcrPipeline(mistral_api_key=MISTRAL_API_KEY)
    try:
        result = pipeline.process_file(saved_path)
    except Exception as e:
        await status_msg.edit_text(f"Ошибка OCR: {e}")
        return

    products = result.products

    await status_msg.edit_text(
        f"Распознано {len(products)} товаров. Сохраняю..."
    )

    try:
        excel_path = ExcelExporter.export(products)
    except Exception as e:
        await status_msg.edit_text(f"Ошибка экспорта: {e}")
        return

    record = DocumentRecord.create_now(
        supplier="",
        source_filename=filename,
        items_count=len(products),
        excel_path=str(excel_path),
    )
    record_id = db.add_record(record)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть на сайте", url=f"{WEB_URL}")],
    ])

    await status_msg.edit_text(
        f"Накладная обработана!\n\n"
        f"Найдено товаров: {len(products)}\n"
        f"Сохранено в: #{record_id}\n\n"
        f"Excel файл: {excel_path.name}",
        reply_markup=keyboard,
    )


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    await process_document(message, photo.file_id, f"photo_{message.message_id}.jpg")


@dp.message(F.document)
async def handle_document(message: types.Message):
    doc = message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        await process_document(message, doc.file_id, doc.file_name or f"doc_{message.message_id}.jpg")
    elif doc.mime_type == "application/pdf":
        await process_document(message, doc.file_id, doc.file_name or f"doc_{message.message_id}.pdf")
    else:
        await message.answer("Поддерживаются только изображения и PDF файлы.")


async def main():
    logger.info("Telegram bot starting...")
    await dp.start_polling(_get_bot())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
