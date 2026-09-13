"""认证与鉴权核心(account-auth 能力).

- 口令哈希:PBKDF2-SHA256(标准库,格式 $akm-pbkdf2$<iter>$<salt>$<hash>)
- 会话:JWT(HS256,24h),密钥 AKM_SECRET_KEY 或 data/secret.key
- 凭证解析:JWT(用户)/ API Token(akm_ 前缀)/ 节点 token(uuid4 hex)三态统一
- require_auth 依赖工厂:路由按需声明最低角色与是否放行节点凭证
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, settings
from app.db import async_session, get_session
from app.models import ApiToken, Node, User

_PBKDF2_ITERATIONS = 210_000
_ACCESS_TOKEN_EXPIRE = timedelta(hours=24)


# ---------------- 口令哈希 ----------------


def hash_password(password: str) -> str:
    """生成 PBKDF2-SHA256 口令哈希."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), _PBKDF2_ITERATIONS
    ).hex()
    return f"$akm-pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验口令哈希."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 5 or parts[1] != "akm-pbkdf2":
            return False
        iterations, salt, expected = int(parts[2]), parts[3], parts[4]
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
        ).hex()
        return secrets.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


# ---------------- JWT 会话 ----------------


def _secret_key() -> bytes:
    """JWT 密钥:优先环境配置,否则首次生成并持久化."""
    if settings.secret_key:
        return settings.secret_key.encode("utf-8")
    key_file = BASE_DIR / "data" / "secret.key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        return key_file.read_bytes().strip()
    key = secrets.token_hex(32)
    key_file.write_bytes(key.encode("utf-8"))
    return key.encode("utf-8")


def create_access_token(username: str, role: str) -> str:
    """签发 24h JWT."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + _ACCESS_TOKEN_EXPIRE,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """校验并解码 JWT,失败返回 None."""
    try:
        return jwt.decode(token, _secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------- 凭证解析 ----------------


@dataclass
class Principal:
    """已认证主体."""

    kind: str  # "user" | "api_token" | "node"
    role: str  # "admin" | "viewer" | "node"
    username: Optional[str] = None
    node_id: Optional[str] = None
    api_token_id: Optional[int] = None


async def resolve_principal(token: str, session: AsyncSession) -> Optional[Principal]:
    """按 JWT / API Token / 节点 token 顺序解析凭证."""
    # 1) JWT(形如 xxx.yyy.zzz,不含 akm_ 前缀)
    claims = decode_access_token(token)
    if claims:
        result = await session.execute(
            select(User).where(User.username == claims.get("sub"), User.disabled.is_(False))
        )
        user = result.scalar_one_or_none()
        if user:
            return Principal(kind="user", role=user.role, username=user.username)
        return None

    # 2) API Token(akm_ 前缀)
    if token.startswith("akm_"):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        result = await session.execute(
            select(ApiToken).where(ApiToken.token_hash == token_hash, ApiToken.revoked_at.is_(None))
        )
        api_token = result.scalar_one_or_none()
        if api_token:
            api_token.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            return Principal(
                kind="api_token",
                role=api_token.role,
                username=api_token.name,
                api_token_id=api_token.id,
            )
        return None

    # 3) 节点 token(uuid4 hex)
    result = await session.execute(
        select(Node).where(Node.token == token, Node.disabled.is_(False))
    )
    node = result.scalar_one_or_none()
    if node:
        return Principal(kind="node", role="node", node_id=node.id)
    return None


def require_auth(min_role: str = "viewer", allow_node: bool = False):
    """鉴权依赖工厂.

    min_role: "viewer" 任意用户级凭证可访问; "admin" 仅 admin。
    allow_node: 是否放行节点凭证(仅只读知识端点为 True)。
    """

    async def dependency(
        authorization: Optional[str] = Header(default=None),
        session: AsyncSession = Depends(get_session),
    ) -> Principal:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        token = authorization[7:].strip()
        principal = await resolve_principal(token, session)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid or expired credentials")
        if principal.kind == "node":
            if not allow_node:
                raise HTTPException(status_code=403, detail="Node credentials are read-only")
            if min_role != "viewer":
                raise HTTPException(status_code=403, detail="Admin role required")
            return principal
        if min_role == "admin" and principal.role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return principal

    return dependency


# ---------------- 管理员初始化与恢复 ----------------


async def ensure_admin_user() -> None:
    """首次启动且无用户时创建管理员(env 配置或随机密码打印)."""
    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        username = settings.admin_username or "admin"
        password = settings.admin_password or secrets.token_urlsafe(12)
        session.add(User(username=username, password_hash=hash_password(password), role="admin"))
        await session.commit()
    if settings.admin_password:
        print(f"✅ 已从环境配置创建管理员账号: {username}")
    else:
        print(f"✅ 首次启动已创建管理员账号: {username} / 一次性密码: {password}")
        print("   请立即登录修改密码,或配置 AKM_ADMIN_USERNAME / AKM_ADMIN_PASSWORD")


async def reset_password_cli(username: str, new_password: str) -> bool:
    """本机重置指定账号密码(reset-password 命令入口)."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.password_hash = hash_password(new_password)
        user.disabled = False
        await session.commit()
        return True
