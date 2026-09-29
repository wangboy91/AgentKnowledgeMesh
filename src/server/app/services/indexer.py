"""索引管理器.

职责：
1. 将扫描结果同步到 SQLite
2. 增量更新：hash 对比，只更新变化的文件
3. 清理已删除文件的索引
4. 按「向量化总开关 + RAG 模式」决定是否同步向量存储

同步策略：
- 新文件：INSERT +（仅总开关开启且 auto 时）向量化
- hash 变化：UPDATE +（同上）向量化
- 文件消失：DELETE + 尽力删除向量
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
    rag_mode: str = "manual",
    vectorization_enabled: bool = False,
) -> dict:
    """同步扫描结果到数据库(仅管理 hub 本机 node_id="local" 的文档).

    Args:
        session: 数据库会话
        scanned: 扫描到的文档列表
        rag_mode: RAG 同步模式(auto / manual)
        vectorization_enabled: 向量化总开关(关闭时一律不产生向量载荷)

    Returns:
        同步统计 {created, updated, deleted} 及 vector_ops 载荷
        {upserts, deleted_ids},由调用方决定后台派发。
        初始 rag_status 由 initial_rag_status 统一决定:仅「总开关开启 +
        auto」为 indexed 并派发向量,其余为 not_indexed。
    """
    from app.services.rag.sync import resolve_rag_status, should_auto_index

    # 只对 hub 本机目录(local)作用域操作,绝不因 hub 扫描结果删改节点文档
    result = await session.execute(
        select(Document).where(Document.node_id == "local")
    )
    existing = {doc.path: doc for doc in result.scalars().all()}

    scanned_paths = {doc.path for doc in scanned}
    stats = {"created": 0, "updated": 0, "deleted": 0}
    changed_paths: list[str] = []  # created/updated 的路径(入库取 id)

    rag_status = resolve_rag_status(None, rag_mode, vectorization_enabled)
    auto_index = should_auto_index(rag_mode, vectorization_enabled)

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
                # 用户显式 excluded 的文档不被内容变更拉回
                old_doc.rag_status = resolve_rag_status(
                    old_doc.rag_status, rag_mode, vectorization_enabled
                )
                stats["updated"] += 1
                changed_paths.append(doc.path)
        else:
            # 新文档，插入
            new_doc = Document(
                path=doc.path,
                title=doc.title,
                hash=doc.hash,
                size=doc.size,
                content=doc.content,
                rag_status=rag_status,
            )
            session.add(new_doc)
            stats["created"] += 1
            changed_paths.append(doc.path)

    # 删除已不存在的文档(仅 local 作用域,绝不触及节点文档;删除前捕获 id 供向量清理)
    paths_to_delete = set(existing.keys()) - scanned_paths
    deleted_ids: list[int] = []
    if paths_to_delete:
        deleted_ids = [existing[p].id for p in paths_to_delete]
        await session.execute(
            delete(Document).where(
                Document.node_id == "local",
                Document.path.in_(paths_to_delete),
            )
        )
        stats["deleted"] = len(paths_to_delete)

    # flush 使新增文档获得 id,构建向量载荷(commit 前避免回滚后派发)
    await session.flush()
    upserts = []
    if auto_index:
        for path in changed_paths:
            doc = existing.get(path)
            if doc is None:
                # 本轮新插入的文档不在 existing 中,flush 后按 (node_id, path)
                # 查询取 id——必须限定 local,否则同路径节点文档会误取(id
                # 归属错误)或使 scalar_one_or_none 抛 MultipleResultsFound
                row = await session.execute(
                    select(Document).where(
                        Document.node_id == "local",
                        Document.path == path,
                    )
                )
                doc = row.scalar_one_or_none()
            if doc is not None and doc.content and doc.rag_status != "excluded":
                upserts.append({
                    "doc_id": doc.id,
                    "title": doc.title,
                    "path": doc.path,
                    "content": doc.content,
                    "node_id": doc.node_id,
                })

    await session.commit()
    return {**stats, "vector_ops": {"upserts": upserts, "deleted_ids": deleted_ids}}
