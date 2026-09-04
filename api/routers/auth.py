from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.auth import AuthService, decode_access_token
from core.repositories import UserRepo
from core.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user: dict
    token: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str = ""
    role: str = "operator"
    store_id: int | None = None


async def get_current_user(request: Request) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await UserRepo.get_by_id(int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_store_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    try:
        user, token = await AuthService.login(req.username, req.password)
        return LoginResponse(user=user.to_dict(), token=token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register")
async def register(req: RegisterRequest, admin: User = Depends(require_admin)):
    try:
        user = await AuthService.register(
            username=req.username,
            password=req.password,
            full_name=req.full_name,
            role=req.role,
            store_id=req.store_id,
        )
        return user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return user.to_dict()
