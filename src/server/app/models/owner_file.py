"""严格 owner 模式元数据表；没有正文、分块、向量或历史正文列。"""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class OwnerFile(Base):
    __tablename__ = 'owner_files'
    file_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(36), index=True)
    root_id: Mapped[str] = mapped_column(String(36))
    path: Mapped[str] = mapped_column(String(1024))
    generation: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_metadata(self):
        return {name:getattr(self,name) for name in ('file_id','owner','root_id','path','generation','revision','hash','size','deleted','available')}


class OwnerReadGrant(Base):
    __tablename__ = 'owner_read_grants'
    file_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(String(256), primary_key=True)
    generation: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class OwnerVersion(Base):
    __tablename__ = 'owner_versions'
    file_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    hash: Mapped[str] = mapped_column(String(64))
    deleted: Mapped[bool] = mapped_column(Boolean)
