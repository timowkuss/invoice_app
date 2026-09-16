"""PostgreSQL in production; SQLite for local installation and tests."""
from __future__ import annotations
import asyncio
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
import asyncpg
from core.config import ROOT

_pool = None
_sqlite = None
_lock = None
_current = ContextVar('db_transaction', default=None)

class LocalConnection:
    def __init__(self, db):
        self.db = db

    async def _run(self, sql, args):
        values = []
        def bind(match):
            value = args[int(match[1]) - 1]
            values.append(str(value) if isinstance(value, Decimal) else value)
            return '?'
        sql = re.sub(r'\$(\d+)', bind, sql)
        sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', sql, flags=re.I)
        sql = re.sub(r'\bILIKE\b', 'LIKE', sql, flags=re.I)
        def execute():
            cursor = self.db.execute(sql, values)
            rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
            for row in rows:
                for key, value in row.items():
                    if value and isinstance(value, str) and key.endswith('_at'):
                        row[key] = datetime.fromisoformat(value)
                    elif value and isinstance(value, str) and key == 'document_date':
                        row[key] = date.fromisoformat(value)
            return rows, cursor.rowcount
        return await asyncio.to_thread(execute)

    async def fetch(self, sql, *args):
        return (await self._run(sql, args))[0]

    async def fetchrow(self, sql, *args):
        rows = await self.fetch(sql, *args)
        return rows[0] if rows else None

    async def fetchval(self, sql, *args):
        row = await self.fetchrow(sql, *args)
        return next(iter(row.values())) if row else None

    async def execute(self, sql, *args):
        _, count = await self._run(sql, args)
        return f'{sql.strip().split()[0].upper()} {count}'

async def init_db(dsn, min_size=2, max_size=10):
    global _pool, _sqlite, _lock
    if dsn.startswith('sqlite:///'):
        path = dsn[len('sqlite:///'):]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _sqlite = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        _sqlite.row_factory = sqlite3.Row
        _sqlite.execute('PRAGMA foreign_keys=ON')
        _sqlite.execute('PRAGMA journal_mode=WAL')
        _sqlite.create_function('lower', 1, lambda s: s.casefold() if s else s)
        _lock = asyncio.Lock()
        _sqlite.executescript((ROOT / 'migrations/sqlite.sql').read_text(encoding='utf-8-sig'))
        ai_columns = {row[1] for row in _sqlite.execute('PRAGMA table_info(ai_requests)').fetchall()}
        if 'pages' not in ai_columns:
            _sqlite.execute('ALTER TABLE ai_requests ADD COLUMN pages INTEGER DEFAULT 0')
    else:
        _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(7182934)')
                await conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)')
                for path in sorted((ROOT / 'migrations').glob('[0-9]*.sql')):
                    if not await conn.fetchval('SELECT 1 FROM schema_migrations WHERE name=$1', path.name):
                        await conn.execute(path.read_text(encoding='utf-8'))
                        await conn.execute('INSERT INTO schema_migrations VALUES ($1)', path.name)
    return _pool

async def close_db():
    global _pool, _sqlite
    if _pool:
        await _pool.close()
        _pool = None
    if _sqlite:
        _sqlite.close()
        _sqlite = None

def get_pool():
    if not _pool:
        raise RuntimeError('PostgreSQL pool unavailable')
    return _pool

@asynccontextmanager
async def get_connection():
    if _current.get() is not None:
        yield _current.get()
    elif _sqlite:
        async with _lock:
            yield LocalConnection(_sqlite)
    else:
        async with get_pool().acquire() as conn:
            yield conn

@asynccontextmanager
async def get_transaction():
    if _current.get() is not None:
        yield _current.get()
        return
    async with get_connection() as conn:
        token = _current.set(conn)
        try:
            if isinstance(conn, LocalConnection):
                await conn.execute('BEGIN IMMEDIATE')
                try:
                    yield conn
                    await conn.execute('COMMIT')
                except BaseException:
                    await conn.execute('ROLLBACK')
                    raise
            else:
                async with conn.transaction():
                    yield conn
        finally:
            _current.reset(token)
