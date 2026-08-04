"""数据库连接管理.

支持 SQLite 和 PostgreSQL 两种数据库。
通过 AV_DB_TYPE 环境变量切换。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings


def create_engine():
    """根据配置创建数据库引擎."""
    kwargs = {"echo": settings.debug}

    if settings.db_type == "sqlite":
        # SQLite 需要 check_same_thread=False
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_async_engine(settings.db_url, **kwargs)


# 创建异步引擎
engine = create_engine()

# 创建会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 基类."""
    pass


async def init_db() -> None:
    """初始化数据库，创建所有表."""
    async with engine.begin() as conn:
        from models.document import Document  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """获取数据库会话（用于依赖注入）."""
    async with async_session() as session:
        yield session


async def close_db() -> None:
    """关闭数据库连接."""
    await engine.dispose()
