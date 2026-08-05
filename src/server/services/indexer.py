"""索引管理器.

职责：
1. 将扫描结果同步到 SQLite
2. 增量更新：hash 对比，只更新变化的文件
3. 清理已删除文件的索引

同步策略：
- 新文件：INSERT
- hash 变化：UPDATE
- 文件消失：DELETE
"""

import json

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import Document
from services.scanner import ScannedDocument


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
        await session.execute(
            delete(Document).where(Document.path.in_(paths_to_delete))
        )
        stats["deleted"] = len(paths_to_delete)

    await session.commit()
    return stats
