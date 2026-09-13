"""API Token 数据模型.

对应 account-auth 能力(api_tokens 表):
- name: 名称(展示用)
- token_hash: SHA256(token) 十六进制,库中只存哈希
- token_prefix: 明文前 8 字符,列表脱敏展示
- role: 凭证角色(admin / viewer),鉴权时视同同角色用户
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiToken(Base):
    """API Token 模型."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
