"""节点数据模型.

对应设计文档中的 nodes 表：
- id: 主键 (UUID)
- name: 节点名称，如 "MacBook-Pro"
- platform: 平台 (darwin/windows/linux)
- ip: 节点IP地址
- status: 状态 (online/offline)
- last_heartbeat: 最后心跳时间
- token: 认证令牌
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Node(Base):
    """节点模型."""

    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # darwin/windows/linux
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="offline")  # online/offline
    token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: uuid.uuid4().hex)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "ip": self.ip,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
