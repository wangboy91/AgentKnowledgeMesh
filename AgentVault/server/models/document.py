"""文档数据模型.

对应设计文档中的 documents 表：
- id: 主键
- path: 文件相对路径（唯一）
- title: 文档标题（首行 # 或文件名）
- hash: 文件 SHA256，用于变更检测
- size: 文件大小（字节）
- tags: JSON 标签列表
- content: 文件全文内容
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Document(Base):
    """文档索引模型."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON array as string
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self, include_content: bool = False) -> dict:
        """转换为字典."""
        import json
        result = {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "hash": self.hash,
            "size": self.size,
            "tags": json.loads(self.tags) if self.tags else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            result["content"] = self.content
        return result
