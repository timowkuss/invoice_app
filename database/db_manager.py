"""
database/db_manager.py

Работа с SQLite базой данных истории обработанных накладных.
Один класс отвечает за все операции: создание таблицы, добавление,
чтение и удаление записей истории.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from config.config import DATABASE_FILE
from models.document import DocumentRecord

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    supplier TEXT,
    source_filename TEXT,
    items_count INTEGER,
    excel_path TEXT
)
"""


class DatabaseManager:
    """Инкапсулирует все обращения к SQLite базе данных истории."""

    def __init__(self, db_path: Path = DATABASE_FILE) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_connection() as conn:
                conn.execute(_CREATE_TABLE_SQL)
                conn.commit()
            logger.info("База данных истории инициализирована: %s", self._db_path)
        except sqlite3.Error as exc:
            logger.error("Ошибка инициализации базы данных: %s", exc)
            raise

    def add_record(self, record: DocumentRecord) -> int:
        """Добавляет запись истории и возвращает ее id."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO history (date, supplier, source_filename, items_count, excel_path)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (record.date, record.supplier, record.source_filename, record.items_count, record.excel_path),
                )
                conn.commit()
                new_id = cursor.lastrowid
                logger.info("Добавлена запись истории id=%s", new_id)
                return new_id
        except sqlite3.Error as exc:
            logger.error("Ошибка добавления записи истории: %s", exc)
            raise

    def get_all_records(self) -> list[DocumentRecord]:
        """Возвращает всю историю, отсортированную от новых к старым."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT * FROM history ORDER BY id DESC").fetchall()
                return [self._row_to_record(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Ошибка чтения истории: %s", exc)
            return []

    def get_record(self, record_id: int) -> DocumentRecord | None:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM history WHERE id = ?", (record_id,)).fetchone()
                return self._row_to_record(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Ошибка чтения записи истории id=%s: %s", record_id, exc)
            return None

    def delete_record(self, record_id: int) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
                conn.commit()
                logger.info("Удалена запись истории id=%s", record_id)
                return True
        except sqlite3.Error as exc:
            logger.error("Ошибка удаления записи истории id=%s: %s", record_id, exc)
            return False

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            date=row["date"],
            supplier=row["supplier"] or "",
            source_filename=row["source_filename"] or "",
            items_count=row["items_count"] or 0,
            excel_path=row["excel_path"] or "",
        )
