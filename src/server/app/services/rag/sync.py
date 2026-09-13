"""统一向量索引通道(services/rag/sync.py).

所有触发向量索引的入口(节点上传、本地扫描、文档 API、RAG 勾选)均经由本模块,
消除各处内嵌的向量维护重复实现。向量操作失败仅告警,不影响主流程;
仅 200 已提交的文档才会派发后台通道(由调用方保证)。

rag_status 状态机:勾选"加入 RAG"→ pending →(后台向量化成功)→ indexed;
移出 → excluded + 删向量。节点上传/扫描按 RAG 模式设定初始状态:
auto → indexed(自动向量化);manual → excluded(不产生向量操作)。
"""

import asyncio
import logging

from app.models.document import Document
from app.services.rag import vector_store

logger = logging.getLogger(__name__)

# RAG 同步模式(持久化于 app_settings 表)
DEFAULT_RAG_MODE = "auto"
VALID_RAG_MODES = ("auto", "manual")


# ---- RAG 同步模式读写 ----

async def get_rag_mode(session) -> str:
    """读取全局 RAG 同步模式(缺省 auto)."""
    from app.models.settings import AppSetting

    row = await session.get(AppSetting, "rag_sync_mode")
    if row is not None and row.value in VALID_RAG_MODES:
        return row.value
    return DEFAULT_RAG_MODE


async def set_rag_mode(session, mode: str) -> None:
    """写入 RAG 同步模式(调用方保证 mode 合法)."""
    from app.models.settings import AppSetting

    row = await session.get(AppSetting, "rag_sync_mode")
    if row is None:
        session.add(AppSetting(key="rag_sync_mode", value=mode))
    else:
        row.value = mode
    await session.commit()


# ---- 向量操作(同步基元,经线程池执行) ----

def index_documents_blocking(upserts: list[dict]) -> None:
    """逐篇向量化(add_document 内部先删旧向量再写入);单篇失败仅告警继续."""
    for doc in upserts:
        try:
            vector_store.add_document(
                doc_id=doc["doc_id"],
                title=doc["title"],
                path=doc["path"],
                content=doc["content"],
                node_id=doc["node_id"],
            )
        except Exception:
            logger.warning(
                "Vector index update failed for doc %s", doc.get("doc_id"), exc_info=True
            )


def remove_documents_blocking(doc_ids: list[int]) -> None:
    """逐篇删除向量分块;失败仅告警继续."""
    for doc_id in doc_ids:
        try:
            vector_store.delete_document(doc_id)
        except Exception:
            logger.warning("Vector index cleanup failed for doc %s", doc_id, exc_info=True)


async def sync_index_and_mark(documents: list[dict], deleted_ids: list[int]) -> None:
    """后台统一通道:线程池执行向量增删,嵌入完成后把 pending 文档回写 indexed.

    documents 条目可选携带 "pending": True,用于勾选加入流程的状态推进;
    节点上传/扫描通道不带该键(初始状态已按模式在入库时设定)。
    """
    if documents:
        await asyncio.to_thread(index_documents_blocking, documents)
        pending_ids = [d["doc_id"] for d in documents if d.get("pending")]
        if pending_ids:
            await _mark_indexed(pending_ids)
    if deleted_ids:
        await asyncio.to_thread(remove_documents_blocking, deleted_ids)


async def _mark_indexed(doc_ids: list[int]) -> None:
    """把 pending 文档回写为 indexed(独立短会话,后台执行)."""
    from app.db import async_session

    async with async_session() as session:
        for doc_id in doc_ids:
            doc = await session.get(Document, doc_id)
            if doc is not None and doc.rag_status == "pending":
                doc.rag_status = "indexed"
        await session.commit()