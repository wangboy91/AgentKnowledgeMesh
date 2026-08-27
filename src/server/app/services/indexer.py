"""索引管理器.

职责：
1. 将扫描结果同步到 SQLite
2. 增量更新：hash 对比，只更新变化的文件
3. 清理已删除文件的索引
4. 同步更新向量存储

同步策略：
- 新文件：INSERT + 向量化
- hash 变化：UPDATE + 向量化
- 文件消失：DELETE + 删除向量
"""

import json
import logging

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.scanner import ScannedDocument

logger = logging.getLogger(__name__)


async def sync_documents(
    session: AsyncSession,
    scanned: list[ScannedDocument],
) -> dict:
    """同步扫描结果到数据库.

    Args:
        session: 数据库会话
        scanned: 扫描到的文档列表

    Returns:
        同步统计 {created, updated, deleted}
    """
    # 获取现有索引
    result = await session.execute(select(Document))
    existing = {doc.path: doc for doc in result.scalars().all()}

    scanned_paths = {doc.path for doc in scanned}
    stats = {"created": 0, "updated": 0, "deleted": 0}

    # 处理扫描到的文档
    for doc in scanned:
        if doc.path in existing:
            # 已存在，检查 hash 是否变化
            old_doc = existing[doc.path]
            if old_doc.hash != doc.hash:
                old_doc.title = doc.title
                old_doc.hash = doc.hash
                old_doc.size = doc.size
                old_doc.content = doc.content
                stats["updated"] += 1

                # 更新向量存储
                try:
                    from app.services.rag.vector_store import add_document
                    add_document(
                        doc_id=old_doc.id,
                        title=old_doc.title,
                        path=old_doc.path,
                        content=old_doc.content,
                        node_id=old_doc.node_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to update vector for {doc.path}: {e}")
        else:
            # 新文档，插入
            new_doc = Document(
                path=doc.path,
                title=doc.title,
                hash=doc.hash,
                size=doc.size,
                content=doc.content,
            )
            session.add(new_doc)
            stats["created"] += 1

    # 删除已不存在的文档
    paths_to_delete = set(existing.keys()) - scanned_paths
    if paths_to_delete:
        # 先删除向量
        for path in paths_to_delete:
            doc = existing[path]
            try:
                from app.services.rag.vector_store import delete_document
                delete_document(doc.id)
            except Exception as e:
                logger.warning(f"Failed to delete vector for {path}: {e}")

        await session.execute(
            delete(Document).where(Document.path.in_(paths_to_delete))
        )
        stats["deleted"] = len(paths_to_delete)

    await session.commit()

    # 为新文档添加向量（需要先 commit 获取 ID）
    if stats["created"] > 0:
        try:
            from app.services.rag.vector_store import add_document
            # 重新查询新添加的文档
            result = await session.execute(select(Document))
            all_docs = {doc.path: doc for doc in result.scalars().all()}

            for doc in scanned:
                if doc.path not in existing:
                    db_doc = all_docs.get(doc.path)
                    if db_doc and db_doc.content:
                        add_document(
                            doc_id=db_doc.id,
                            title=db_doc.title,
                            path=db_doc.path,
                            content=db_doc.content,
                            node_id=db_doc.node_id,
                        )
        except Exception as e:
            logger.warning(f"Failed to add vectors for new documents: {e}")

    return stats
