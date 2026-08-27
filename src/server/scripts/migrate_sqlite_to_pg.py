"""一次性迁移脚本：SQLite -> PostgreSQL.

将 documents / nodes 表搬迁到 PostgreSQL，保留主键 ID，
向量表（document_vectors）的 doc_id 与之对应，无需重新嵌入。

用法:
    cd src/server
    uv run python scripts/migrate_sqlite_to_pg.py
"""

import asyncio
import sys
from pathlib import Path

# 保证可以从任意 CWD 运行
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import BASE_DIR, settings
from app.db import Base
from app.models.document import Document  # noqa: F401
from app.models.node import Node  # noqa: F401

SQLITE_PATH = BASE_DIR / "data" / "agentvault.db"


async def main():
    if not SQLITE_PATH.exists():
        print(f"❌ SQLite 数据库不存在: {SQLITE_PATH}")
        sys.exit(1)

    # 源：SQLite
    src_engine = create_async_engine(f"sqlite+aiosqlite:///{SQLITE_PATH}")
    # 目标：PostgreSQL（读 AKM_DB_* 配置）
    dst_engine = create_async_engine(settings.db_url)

    # 1. 在 PG 创建表
    async with dst_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PostgreSQL 表已创建")

    src_session = async_sessionmaker(src_engine, expire_on_commit=False)
    dst_session = async_sessionmaker(dst_engine, expire_on_commit=False)

    try:
        async with src_session() as src, dst_session() as dst:
            # 2. 迁移 documents
            docs = (await src.execute(select(Document))).scalars().all()
            for doc in docs:
                dst.add(Document(
                    id=doc.id, node_id=doc.node_id, path=doc.path,
                    title=doc.title, hash=doc.hash, size=doc.size,
                    tags=doc.tags, content=doc.content,
                    created_at=doc.created_at, updated_at=doc.updated_at,
                ))
            await dst.commit()
            print(f"✅ documents 迁移完成: {len(docs)} 行")

            # 3. 迁移 nodes
            nodes = (await src.execute(select(Node))).scalars().all()
            for node in nodes:
                dst.add(Node(
                    id=node.id, name=node.name, platform=node.platform,
                    ip=node.ip, status=node.status, token=node.token,
                    last_heartbeat=node.last_heartbeat,
                    created_at=node.created_at, updated_at=node.updated_at,
                ))
            await dst.commit()
            print(f"✅ nodes 迁移完成: {len(nodes)} 行")

            # 4. 校验
            pg_count = await dst.execute(
                text("SELECT COUNT(*) FROM documents"))
            print(f"✅ PostgreSQL documents 总数: {pg_count.scalar()}")

        # 5. 重置自增序列（PG 需要显式对齐，否则新插入会主键冲突）
        async with dst_engine.begin() as conn:
            await conn.execute(text(
                "SELECT setval('documents_id_seq', "
                "(SELECT COALESCE(MAX(id), 0) + 1 FROM documents), false)"
            ))
        print("✅ documents_id_seq 序列已对齐")
    finally:
        await src_engine.dispose()
        await dst_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
