"""API Token 服务(account-auth 能力).

创建 / 轮换时生成一次性明文(akm_ 前缀),库中仅存 SHA256 哈希与前缀脱敏展示;
吊销后立即失效(解析侧按 revoked_at 过滤)。

生命周期:`create` → (`rotate` 换密钥,记录不变) → `revoke`(软删,留审计) → `purge`(硬删)。
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


async def rotate_token(
    session: AsyncSession, token_id: int
) -> Optional[tuple[ApiToken, str]]:
    """轮换 Token:为同一条记录换发新密钥,旧密钥立即失效。

    与「吊销 + 新建」的区别:记录 id / 名称 / 角色 / 创建时间保持不变,
    不会留下一条"已吊销"的残留记录,因此轮换后列表里仍是同一个**有效** Token,
    只是前缀与密钥变了 —— 这是轮换的闭环。

    已吊销的 Token 不允许轮换(轮换不应隐式恢复一个已被主动作废的凭证),
    返回 None 表示记录不存在;对已吊销记录抛 ValueError。
    """
    token = await session.get(ApiToken, token_id)
    if token is None:
        return None
    if token.revoked_at is not None:
        raise ValueError("已吊销的 Token 不可轮换,请重新创建")
    plaintext, token_hash, prefix = _generate_token()
    token.token_hash = token_hash
    token.token_prefix = prefix
    token.last_used_at = None  # 新密钥尚未被使用
    await session.commit()
    await session.refresh(token)
    return token, plaintext


async def purge_token(session: AsyncSession, token_id: int) -> bool:
    """彻底删除 Token 记录(硬删除),返回是否存在.

    与 `revoke_token` 的区别:吊销只置 `revoked_at` 保留审计痕迹;
    彻底删除会移除整行,不可恢复。仅允许删除**已吊销**的 Token,
    避免误删仍在使用的凭证(活跃 Token 必须先吊销再删除)。
    """
    token = await session.get(ApiToken, token_id)
    if token is None:
        return False
    if token.revoked_at is None:
        raise ValueError("仅可删除已吊销的 Token,请先吊销")
    await session.delete(token)
    await session.commit()
    return True

