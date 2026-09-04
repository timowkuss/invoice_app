from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
import jwt

from core.models.user import User
from core.repositories import UserRepo


SECRET_KEY = ""  # Set from .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, role: str, store_id: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "store_id": store_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None


class AuthService:
    @staticmethod
    async def register(
        username: str,
        password: str,
        full_name: str = "",
        role: str = "operator",
        store_id: int | None = None,
        telegram_chat_id: int | None = None,
    ) -> User:
        existing = await UserRepo.get_by_username(username)
        if existing:
            raise ValueError("Username already exists")

        user = User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            store_id=store_id,
            telegram_chat_id=telegram_chat_id,
        )
        return await UserRepo.create(user)

    @staticmethod
    async def login(username: str, password: str) -> tuple[User, str]:
        user = await UserRepo.get_by_username(username)
        if not user or not user.is_active:
            raise ValueError("Invalid username or password")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password")

        token = create_access_token(user.id, user.role, user.store_id)
        return user, token

    @staticmethod
    async def get_current_user(token: str) -> User | None:
        payload = decode_access_token(token)
        if not payload:
            return None
        user_id = int(payload.get("sub", 0))
        if not user_id:
            return None
        return await UserRepo.get_by_id(user_id)

    @staticmethod
    async def bind_telegram(username: str, chat_id: int) -> User:
        user = await UserRepo.get_by_username(username)
        if not user:
            raise ValueError("User not found")
        await UserRepo.set_telegram(user.id, chat_id)
        user.telegram_chat_id = chat_id
        return user

    @staticmethod
    async def init_super_admin() -> None:
        existing = await UserRepo.get_by_username("admin")
        if not existing:
            await AuthService.register(
                username="admin",
                password="admin",
                full_name="Super Admin",
                role="super_admin",
            )
