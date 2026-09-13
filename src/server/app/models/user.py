"""用户账号数据模型.

对应 account-auth 能力(users 表):
- id: 主键
- username: 用户名(唯一)
- password_hash: 口令哈希(PBKDF2-SHA256)
- role: 角色(admin / viewer)
- disabled: 账号是否禁用
"""

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """用户账号模型."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "disabled": self.disabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
