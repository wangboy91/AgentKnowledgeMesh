"""统一向量索引通道(services/rag/sync.py).

所有触发向量索引的入口(节点上传、本地扫描、文档 API、RAG 勾选)均经由本模块,
消除各处内嵌的向量维护重复实现。向量操作失败仅告警,不影响主流程;
仅 200 已提交的文档才会派发后台通道(由调用方保证)。

rag_status 四态(见 vector-search 规范):
- ``not_indexed`` 尚未向量化——默认态(向量化总开关关闭,或 manual 模式下的新文档)
- ``pending``     已勾选/排队,等待后台嵌入
- ``indexed``     已入向量库,可被语义检索召回
- ``excluded``    用户显式移出,不参与语义检索

入库初始状态由「向量化总开关 + rag_sync_mode」共同决定,统一走
:func:`initial_rag_status`:仅「总开关开启 + auto」自动向量化,其余一律
``not_indexed``。勾选"加入 RAG"→ ``pending`` →(后台向量化成功)→ ``indexed``;
移出 → ``excluded`` + 删向量。
"""

import asyncio
import logging

from app.models.document import Document
from app.services.rag import vector_store

logger = logging.getLogger(__name__)

# RAG 同步模式(持久化于 app_settings 表);默认 manual:向量化默认关闭,
# 需要自动入库的部署在设置页显式切回 auto
DEFAULT_RAG_MODE = "manual"
VALID_RAG_MODES = ("auto", "manual")

# 向量化总开关(持久化于 app_settings 表);默认关闭:不初始化向量库、
# 不产生嵌入调用,语义检索降级为关键词检索
DEFAULT_VECTORIZATION_ENABLED = False


# ---- 全局设置读写 ----

async def _get_setting(session, key: str, default: str) -> str:
    """读取 app_settings 单键(缺省返回 default)."""
    from app.models.settings import AppSetting

    row = await session.get(AppSetting, key)
    return row.value if row is not None else default


async def _set_setting(session, key: str, value: str) -> None:
    """写入 app_settings 单键(调用方保证 value 合法)."""
    from app.models.settings import AppSetting

    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def get_rag_mode(session) -> str:
    """读取全局 RAG 同步模式(缺省 manual)."""
    value = await _get_setting(session, "rag_sync_mode", DEFAULT_RAG_MODE)
    return value if value in VALID_RAG_MODES else DEFAULT_RAG_MODE


async def set_rag_mode(session, mode: str) -> None:
    """写入 RAG 同步模式(调用方保证 mode 合法)."""
    await _set_setting(session, "rag_sync_mode", mode)


async def get_vectorization_enabled(session) -> bool:
    """读取向量化总开关(缺省关闭)."""
    value = await _get_setting(
        session,
        "vectorization_enabled",
        "true" if DEFAULT_VECTORIZATION_ENABLED else "false",
    )
    return value == "true"


async def set_vectorization_enabled(session, enabled: bool) -> None:
    """写入向量化总开关(不清理既有向量;关闭后重新开启即可复用)."""
    await _set_setting(session, "vectorization_enabled", "true" if enabled else "false")


# ---- 入库状态策略(三个入库通道共用) ----

def initial_rag_status(rag_mode: str, vectorization_enabled: bool) -> str:
    """决定新/变更文档的初始 rag_status.

    仅「向量化总开关开启 + auto 模式」自动向量化(→ ``indexed``),
    其余组合一律 ``not_indexed``(尚未向量化,等待手动操作)。
    """
    return "indexed" if should_auto_index(rag_mode, vectorization_enabled) else "not_indexed"


def resolve_rag_status(
    existing_status: str | None, rag_mode: str, vectorization_enabled: bool
) -> str:
    """变更文档的 rag_status:用户显式 ``excluded`` 的文档保持 excluded.

    ``excluded`` 表达的是用户意图(「这篇不要进语义检索」),不应因文件内容
    变更或重新扫描被静默拉回;其余状态按 :func:`initial_rag_status` 重算。
    """
    if existing_status == "excluded":
        return "excluded"
    return initial_rag_status(rag_mode, vectorization_enabled)


def should_auto_index(rag_mode: str, vectorization_enabled: bool) -> bool:
    """是否应自动派发向量操作(总开关开启且模式为 auto)."""
    return vectorization_enabled and rag_mode == "auto"


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

    documents 条目可选携带 "pending": True,用于勾选加入/全量索引/补齐流程的
    状态推进;节点上传/扫描通道不带该键(初始状态已按策略在入库时设定)。
    """
    if documents:
        await asyncio.to_thread(index_documents_blocking, documents)
        pending_ids = [d["doc_id"] for d in documents if d.get("pending")]
        if pending_ids:
            await _mark_indexed(pending_ids)
    if deleted_ids:
        await asyncio.to_thread(remove_documents_blocking, deleted_ids)


async def collect_backfill_payload(session) -> list[dict]:
    """收集待向量化文档载荷(非 excluded 且有内容),并把非 indexed 的置 pending.

    供全量索引(``POST /api/rag/index``)与「进入 auto+开启组合」时的后台补齐共用;
    已 indexed 的文档仍纳入载荷(重新嵌入即覆盖),但不改状态。
    调用方负责 commit 与后台派发。
    """
    from sqlalchemy import select

    result = await session.execute(
        select(Document).where(
            Document.rag_status != "excluded",
            Document.content.is_not(None),
        )
    )
    payload: list[dict] = []
    for doc in result.scalars().all():
        if not doc.content:
            continue
        if doc.rag_status != "indexed":
            doc.rag_status = "pending"
        payload.append({
            "doc_id": doc.id,
            "title": doc.title,
            "path": doc.path,
            "content": doc.content,
            "node_id": doc.node_id,
            "pending": True,
        })
    await session.commit()
    return payload


async def _mark_indexed(doc_ids: list[int]) -> None:
    """把 pending 文档回写为 indexed(独立短会话,后台执行)."""
    from app.db import async_session

    async with async_session() as session:
        for doc_id in doc_ids:
            doc = await session.get(Document, doc_id)
            if doc is not None and doc.rag_status == "pending":
                doc.rag_status = "indexed"
        await session.commit()
