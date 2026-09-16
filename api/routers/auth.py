from __future__ import annotations
import asyncio
import hashlib
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from core.auth import AuthService, decode_access_token, hash_password, normalize_email
from core.database import get_transaction
from core.repositories import UserRepo, StoreRepo
from core.models.user import User
from core import mailer

router = APIRouter()

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

class RegisterRequest(LoginRequest):
    full_name: str = Field(default='', max_length=255)
    role: Literal['operator', 'store_admin'] = 'operator'
    store_id: int | None = None

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=10, max_length=72)

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
        user, token = await AuthService.login(req.email, req.password)
    except ValueError:
        raise HTTPException(401, 'Неверный email или пароль')
    return session_response(response, user, token)

@router.post('/forgot-password')
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    await throttle(request, 'password-reset')
    if not mailer.is_configured():
        raise HTTPException(503, 'Восстановление пароля пока не настроено. Обратитесь к администратору.')
    user = await UserRepo.get_by_email(req.email)
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        async with get_transaction() as conn:
            await conn.execute('DELETE FROM password_reset_tokens WHERE user_id=$1 AND used_at IS NULL', user.id)
            await conn.execute(
                'INSERT INTO password_reset_tokens (user_id,token_hash,expires_at) VALUES ($1,$2,$3)',
                user.id, token_hash, expires_at,
            )
        reset_url = f"{os.getenv('WEB_URL','http://localhost:8000').rstrip('/')}/?{urlencode({'reset_token': token})}"
        try:
            await asyncio.to_thread(mailer.send_password_reset_email, req.email, reset_url)
        except Exception:
            logging.getLogger(__name__).exception('Password reset email delivery failed')
    return {'message': 'Если такой email зарегистрирован, мы отправили ссылку для сброса пароля.'}

@router.post('/reset-password')
async def reset_password(req: ResetPasswordRequest, request: Request):
    await throttle(request, 'password-reset-confirm')
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    password_hash = await asyncio.to_thread(hash_password, req.password)
    async with get_transaction() as conn:
        row = await conn.fetchrow(
            'SELECT id,user_id FROM password_reset_tokens WHERE token_hash=$1 AND used_at IS NULL AND expires_at>$2',
            token_hash, datetime.utcnow(),
        )
        if not row:
            raise HTTPException(400, 'Ссылка недействительна или срок её действия истёк')
        await UserRepo.set_password(row['user_id'], password_hash)
        await conn.execute('UPDATE password_reset_tokens SET used_at=NOW() WHERE id=$1', row['id'])
    return {'message': 'Пароль изменён. Теперь можно войти.'}

@router.post('/logout')
async def logout(response: Response):
    response.delete_cookie('invoice_session', path='/')
    return {'status':'ok'}

@router.get('/me')
async def me(user: User = Depends(get_current_user)):
    return user.to_dict()

@router.post('/register', status_code=201)
async def register(req: RegisterRequest, admin: User = Depends(require_super_admin)):
    store_id = req.store_id
    if not store_id:
        raise HTTPException(422, 'Укажите магазин')
    if store_id and not await StoreRepo.get_by_id(store_id):
        raise HTTPException(404, 'Магазин не найден')
    try:
        return (await AuthService.register(req.email, req.password, req.full_name, req.role, store_id)).to_dict()
    except ValueError as exc:
        raise HTTPException(409, str(exc))
