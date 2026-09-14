"""向独立 SQLite 库注入大规模文档树数据(懒加载/压缩性能验证用)。

测试/验证内容:
- GET /api/documents/tree 全量模式 vs GZip vs ?dir= 目录切片的体积/耗时对比
- documents 表 (node_id, path) 索引下单目录切片的查询规模无关性

前置条件:
- 必须以环境变量指向独立库,避免碰开发库:
  AKM_DB_TYPE=sqlite AKM_DB_PATH=data/perf_tree.db

运行方式:
- cd src/server && AKM_DB_TYPE=sqlite AKM_DB_PATH=data/perf_tree.db uv run python scripts/seed_big_tree.py
"""

import asyncio

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import engine, init_db
from app.models.document import Document

# 数据形态:4 个知识根 × 20 个主题目录 × 7 个子目录,共 2 万篇;
# 每 500 篇混入一个含 LIKE 通配字符的文件名
TOTAL = 20_000
ROOTS = 4
TOPICS = 20
SUBS = 7
RAG_CYCLE = ("indexed", "pending", "excluded")


async def main() -> None:
    await init_db()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        await session.execute(delete(Document))
        await session.commit()

    rows = []
    for i in range(TOTAL):
        root = f"kb{i % ROOTS}"
        topic = f"topic-{i % TOPICS}"
        sub = f"sub-{i % SUBS}"
        name = f"100%_done-{i}.md" if i % 500 == 0 else f"doc-{i}.md"
        rows.append(Document(
            node_id="local",
            path=f"{root}/{topic}/{sub}/{name}",
            title=f"Doc {i}",
            hash=f"h{i}",
            size=100,
            content="x" * 100,
            rag_status=RAG_CYCLE[i % 3],
        ))

    async with factory() as session:
        session.add_all(rows)
        await session.commit()
        count = (await session.execute(select(func.count()).select_from(Document))).scalar_one()
    print(f"seeded {count} documents into {engine.url}")

    await engine.dispose()


asyncio.run(main())
