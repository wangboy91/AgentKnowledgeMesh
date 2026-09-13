"""API Token 服务(account-auth 能力).

创建时生成一次性明文(akm_ 前缀),库中仅存 SHA256 哈希与前缀脱敏展示;
吊销后立即失效(解析侧按 revoked_at 过滤)。
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiToken


def _generate_token() -> tuple[str, str, str]:
    """返回 (明文, 哈希, 前缀)."""
    plaintext = "akm_" + secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return plaintext, token_hash, plaintext[:12]


async def create_token(
    session: AsyncSession, name: str, role: str, created_by: Optional[str] = None
) -> tuple[ApiToken, str]:
    """创建 API Token,返回 (记录, 一次性明文)."""
    plaintext, token_hash, prefix = _generate_token()
    token = ApiToken(
        name=name,
        token_hash=token_hash,
        token_prefix=prefix,
        role=role if role in ("admin", "viewer") else "viewer",
        created_by=created_by,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token, plaintext


async def list_tokens(session: AsyncSession) -> list[dict]:
    """列出 Token(脱敏,不含哈希)."""
    result = await session.execute(select(ApiToken).order_by(ApiToken.created_at.desc()))
    return [
        {
            "id": t.id,
            "name": t.name,
            "token_prefix": t.token_prefix,
            "role": t.role,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            "revoked": t.revoked_at is not None,
        }
        for t in result.scalars().all()
    ]


async def revoke_token(session: AsyncSession, token_id: int) -> bool:
    """吊销 Token,返回是否存在."""
    token = await session.get(ApiToken, token_id)
    if token is None or token.revoked_at is not None:
        return False
    token.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return True
