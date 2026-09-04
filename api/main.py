from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.database import init_db, close_db
from core.auth import AuthService


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/invoice_app")
    await init_db(dsn)
    await AuthService.init_super_admin()
    yield
    await close_db()


app = FastAPI(
    title="Invoice App API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routers import auth, documents, products, stores, users, stats, settings, matching

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(stores.router, prefix="/api/stores", tags=["Stores"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(stats.router, prefix="/api/stats", tags=["Stats"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(matching.router, prefix="/api/matching", tags=["Matching"])

app.mount("/static", StaticFiles(directory="web/static"), name="static")
