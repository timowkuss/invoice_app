from __future__ import annotations
import asyncio
import hashlib
import os
import time
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from core.auth import AuthService, decode_access_token, hash_password
from core.database import get_transaction
from core.repositories import UserRepo, StoreRepo
from core.models.user import User
from core.models.store import Store

router = APIRouter()

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9_.@-]+$')
    password: str = Field(min_length=1, max_length=72)

class SignupRequest(LoginRequest):
    store_name: str = Field(min_length=2, max_length=255)
    full_name: str = Field(default='', max_length=255)

class RegisterRequest(LoginRequest):
    full_name: str = Field(default='', max_length=255)
    role: Literal['operator', 'store_admin', 'super_admin'] = 'operator'
    store_id: int | None = None

async def throttle(request: Request, action: str):
    # Persistent counters work across processes. Never trust forwarded headers here.
    key = hashlib.sha256(f'{action}:{request.client.host if request.client else "local"}'.encode()).hexdigest()
    now = time.time()
    async with get_transaction() as conn:
        await conn.execute('INSERT INTO login_attempts (key,attempts,window_start) VALUES ($1,0,$2) ON CONFLICT (key) DO NOTHING', key, now)
        await conn.execute('UPDATE login_attempts SET attempts=0,window_start=$1 WHERE key=$2 AND window_start<$3', now, key, now-900)
        attempts = await conn.fetchval('UPDATE login_attempts SET attempts=attempts+1 WHERE key=$1 RETURNING attempts', key)
    if attempts > (30 if action == 'login' else 5):
        raise HTTPException(429, 'Слишком много попыток. Повторите через 15 минут.', headers={'Retry-After':'900'})

async def get_current_user(request: Request) -> User:
    header = request.headers.get('Authorization', '')
    token = header[7:] if header.startswith('Bearer ') else request.cookies.get('invoice_session', '')
    payload = decode_access_token(token)
    user = await UserRepo.get_by_id(int(payload['sub'])) if payload else None
    if not user or not user.is_active:
        raise HTTPException(401, 'Войдите в аккаунт')
    requested = request.headers.get('X-Store-ID')
    if user.is_super_admin and requested:
        try:
            user.store_id = int(requested)
        except ValueError:
            raise HTTPException(400, 'Неверный магазин')
    if user.store_id is not None:
        store = await StoreRepo.get_by_id(user.store_id)
        if not store or not store.is_active:
            raise HTTPException(403, 'Магазин отключён')
    return user

async def require_store(user: User = Depends(get_current_user)):
    if not user.store_id:
        raise HTTPException(400, 'Выберите магазин')
    return user

async def require_admin(user: User = Depends(get_current_user)):
    if not user.is_store_admin:
        raise HTTPException(403, 'Нужны права администратора магазина')
    return user

async def require_super_admin(user: User = Depends(get_current_user)):
    if not user.is_super_admin:
        raise HTTPException(403, 'Нужны права владельца сервиса')
    return user

def session_response(response, user, token):
    response.set_cookie('invoice_session', token, httponly=True, secure=os.getenv('COOKIE_SECURE','false').lower()=='true', samesite='strict', max_age=86400, path='/')
    return {'user': user.to_dict()}

@router.post('/login')
async def login(req: LoginRequest, request: Request, response: Response):
    await throttle(request, 'login')
    try:
        user, token = await AuthService.login(req.username.lower(), req.password)
    except ValueError:
        raise HTTPException(401, 'Неверный логин или пароль')
    return session_response(response, user, token)

@router.post('/signup', status_code=201)
async def signup(req: SignupRequest, request: Request, response: Response):
    await throttle(request, 'signup')
    if os.getenv('ALLOW_SIGNUP','true').lower() != 'true':
        raise HTTPException(403, 'Регистрация через владельца сервиса')
    try:
        password_hash = await asyncio.to_thread(hash_password, req.password)
        async with get_transaction():
            if await UserRepo.get_by_username(req.username.lower()):
                raise HTTPException(409, 'Этот логин уже занят')
            store = await StoreRepo.create(Store(name=req.store_name.strip(), code=uuid.uuid4().hex[:16]))
            user = await UserRepo.create(User(username=req.username.lower(), password_hash=password_hash, full_name=req.full_name, role='store_admin', store_id=store.id))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    from core.auth import create_access_token
    return session_response(response, user, create_access_token(user.id, user.role, user.store_id))

@router.post('/logout')
async def logout(response: Response):
    response.delete_cookie('invoice_session', path='/')
    return {'status':'ok'}

@router.get('/me')
async def me(user: User = Depends(get_current_user)):
    return user.to_dict()

@router.post('/register', status_code=201)
async def register(req: RegisterRequest, admin: User = Depends(require_admin)):
    if not admin.is_super_admin and (req.role == 'super_admin' or req.store_id not in (None, admin.store_id)):
        raise HTTPException(403, 'Нельзя назначить эти права или другой магазин')
    store_id = req.store_id if admin.is_super_admin else admin.store_id
    if req.role != 'super_admin' and not store_id:
        raise HTTPException(422, 'Укажите магазин')
    if store_id and not await StoreRepo.get_by_id(store_id):
        raise HTTPException(404, 'Магазин не найден')
    try:
        return (await AuthService.register(req.username.lower(), req.password, req.full_name, req.role, store_id)).to_dict()
    except ValueError as exc:
        raise HTTPException(409, str(exc))
