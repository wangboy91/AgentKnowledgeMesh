"""数据库连接管理.

支持 SQLite 和 PostgreSQL 两种数据库。
通过 AKM_DB_TYPE 环境变量切换。
"""

from sqlalchemy import inspect as sql_inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def create_engine():
    """根据配置创建数据库引擎."""
    kwargs = {"echo": settings.debug, "pool_pre_ping": True}

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


# 轻量列迁移:create_all 只建新表不改旧表,存量库在此补列(按方言)
_COLUMN_MIGRATIONS = {
    "postgresql": [
        ("nodes", "disabled", "ALTER TABLE nodes ADD COLUMN disabled BOOLEAN NOT NULL DEFAULT FALSE"),
        ("documents", "rag_status", "ALTER TABLE documents ADD COLUMN rag_status VARCHAR(16) NOT NULL DEFAULT 'indexed'"),
    ],
    "sqlite": [
        ("nodes", "disabled", "ALTER TABLE nodes ADD COLUMN disabled BOOLEAN NOT NULL DEFAULT 0"),
        ("documents", "rag_status", "ALTER TABLE documents ADD COLUMN rag_status VARCHAR(16) NOT NULL DEFAULT 'indexed'"),
    ],
}


async def _migrate_columns() -> None:
    """为存量库补充新增列(已存在则跳过)."""

    def _table_columns(sync_conn):
        insp = sql_inspect(sync_conn)
        return {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}

    migrations = _COLUMN_MIGRATIONS.get(engine.dialect.name, [])
    if not migrations:
        return
    async with engine.begin() as conn:
        tables = await conn.run_sync(_table_columns)
        for table, column, ddl in migrations:
            if table in tables and column not in tables[table]:
                await conn.execute(text(ddl))


async def init_db() -> None:
    """初始化数据库，创建所有表."""
    # 显式导入全部模型,确保注册到 Base.metadata(不依赖包 __init__ 的副作用)
    from app.models import ApiToken, AppSetting, Document, Node, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_columns()


async def get_session() -> AsyncSession:
    """获取数据库会话（用于依赖注入）."""
    async with async_session() as session:
        yield session


async def close_db() -> None:
    """关闭数据库连接."""
    await engine.dispose()
