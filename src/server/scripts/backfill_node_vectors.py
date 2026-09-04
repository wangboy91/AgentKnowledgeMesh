"""一次性回填脚本：为已入库但向量缺失的文档补建向量.

只补缺：跳过向量表中已有分块的文档（如本地文档），仅对缺失者
分块、嵌入并写入向量表。与 POST /api/rag/index 的全量重建互补——
后者对所有文档重新嵌入，本脚本只处理向量表中不存在的文档。

用法:
    cd src/server
    uv run python scripts/backfill_node_vectors.py [--node-id <id>]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 保证可以从任意 CWD 运行
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.document import Document
from app.services.rag import vector_store


async def _load_documents(node_id: str | None) -> list[Document]:
    """从数据库加载文档（可按节点过滤）."""
    engine = create_async_engine(settings.db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            stmt = select(Document)
            if node_id:
                stmt = stmt.where(Document.node_id == node_id)
            return list((await session.execute(stmt)).scalars().all())
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="为已入库但向量表中缺失向量的文档补建向量（只补缺，不重复嵌入）"
    )
    parser.add_argument(
        "--node-id", default=None,
        help="只回填指定节点的文档（默认全部节点）",
    )
    args = parser.parse_args()

    try:
        docs = asyncio.run(_load_documents(args.node_id))
    except Exception as e:
        print(f"❌ 无法读取数据库: {e}")
        sys.exit(1)

    scope = f"node_id={args.node_id}" if args.node_id else "全部节点"
    print(f"数据库文档: {len(docs)} 篇（{scope}）")

    # 只补缺：向量表中已有分块的文档不重复嵌入
    try:
        indexed_ids = vector_store.get_indexed_doc_ids()
    except Exception as e:
        print(f"❌ 无法读取向量表: {e}")
        sys.exit(1)

    pending = [d for d in docs if d.id not in indexed_ids and d.content]
    skipped = len(docs) - len(pending)
    print(f"跳过（已有向量或无内容）: {skipped} 篇，待补建: {len(pending)} 篇")

    backfilled = failed = 0
    for doc in pending:
        try:
            vector_store.add_document(
                doc_id=doc.id,
                title=doc.title,
                path=doc.path,
                content=doc.content,
                node_id=doc.node_id,
            )
            backfilled += 1
        except Exception as e:
            failed += 1
            print(f"  [warn] doc {doc.id} ({doc.path}) 嵌入失败: {type(e).__name__}: {e}")

    print(f"✅ 回填完成: 补建 {backfilled} 篇，跳过 {skipped} 篇，失败 {failed} 篇")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
