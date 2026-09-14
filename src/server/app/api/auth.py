"""认证与账号管理路由(account-auth 能力).

login 公开;其余端点需要凭证:本人改密码 viewer+,用户与 Token 管理 admin。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.api_tokens import create_token, list_tokens, purge_token, revoke_token
from app.services.auth import (
    create_access_token,
    hash_password,
    require_auth,
    verify_password,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdateRequest(BaseModel):
    disabled: Optional[bool] = None
    password: Optional[str] = None
    role: Optional[str] = None


class TokenCreateRequest(BaseModel):
    name: str
    role: str = "viewer"


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """登录,签发 JWT."""
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or user.disabled or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    access_token = create_access_token(user.username, user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    principal=Depends(require_auth("viewer")),
    session: AsyncSession = Depends(get_session),
):
    """修改本人密码."""
    result = await session.execute(select(User).where(User.username == principal.username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    user.password_hash = hash_password(body.new_password)
    await session.commit()
    return {"message": "密码已更新"}


@router.get("/users")
async def list_users(
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """列出用户(admin)."""
    result = await session.execute(select(User).order_by(User.created_at))
    return [u.to_dict() for u in result.scalars().all()]


@router.post("/users")
async def create_user(
    body: UserCreateRequest,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """创建用户(admin)."""
    if body.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="role 必须为 admin 或 viewer")
    exists = await session.execute(select(User).where(User.username == body.username))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.to_dict()


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """禁用/启用、改角色或重置密码(admin)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.disabled is not None and user.role == "admin" and body.disabled:
        admins = await session.execute(
            select(User).where(User.role == "admin", User.disabled.is_(False))
        )
        enabled_admins = [a for a in admins.scalars().all() if a.id != user_id]
        if not enabled_admins:
            raise HTTPException(status_code=400, detail="不能禁用最后一个可用管理员")
    if body.disabled is not None:
        user.disabled = body.disabled
    if body.role is not None:
        if body.role not in ("admin", "viewer"):
            raise HTTPException(status_code=400, detail="role 必须为 admin 或 viewer")
        user.role = body.role
    if body.password:
        user.password_hash = hash_password(body.password)
    await session.commit()
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """删除用户(admin,不能删自己与最后一个可用管理员)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == principal.username:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if user.role == "admin" and not user.disabled:
        admins = await session.execute(
            select(User).where(User.role == "admin", User.disabled.is_(False))
        )
        enabled_admins = [a for a in admins.scalars().all() if a.id != user_id]
        if not enabled_admins:
            raise HTTPException(status_code=400, detail="不能删除最后一个可用管理员")
    await session.delete(user)
    await session.commit()
    return {"message": "已删除"}


@router.get("/tokens")
async def get_tokens(
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """列出 API Token(脱敏,admin)."""
    return await list_tokens(session)


@router.post("/tokens")
async def post_token(
    body: TokenCreateRequest,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """创建 API Token(明文仅本次返回,admin)."""
    if body.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="role 必须为 admin 或 viewer")
    token, plaintext = await create_token(session, body.name, body.role, principal.username)
    data = {
        "id": token.id,
        "name": token.name,
        "token_prefix": token.token_prefix,
        "role": token.role,
        "created_at": token.created_at.isoformat() if token.created_at else None,
        "token": plaintext,
    }
    return data


@router.delete("/tokens/{token_id}")
async def delete_token(
    token_id: int,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """吊销 API Token(admin)."""
    ok = await revoke_token(session, token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Token 不存在或已吊销")
    return {"message": "已吊销"}


@router.delete("/tokens/{token_id}/purge")
async def purge_token_endpoint(
    token_id: int,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """彻底删除已吊销的 API Token(admin,不可恢复)."""
    try:
        ok = await purge_token(session, token_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Token 不存在")
    return {"message": "已彻底删除"}
