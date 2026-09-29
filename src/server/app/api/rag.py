"""RAG API.

提供语义搜索和 RAG 上下文组装功能。

向量化总开关(``vectorization_enabled``,默认关闭)关闭时:
- 语义检索端点**降级为关键词检索**,响应带 ``"mode": "keyword"``(入口始终可用)
- 全量索引与"加入 RAG"返回 409;"移出 RAG"仍放行(仅清理向量)
- 统计端点不连接向量库
"""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.document import Document
from app.services.auth import require_auth
from app.services.rag import vector_store

logger = logging.getLogger(__name__)

router = APIRouter()

VECTORIZATION_DISABLED_DETAIL = "向量化已关闭,请先在设置中开启向量化"


async def _vectorization_enabled(session) -> bool:
    """向量化总开关状态(默认关闭)."""
    from app.services.rag.sync import get_vectorization_enabled

    return await get_vectorization_enabled(session)


async def _excluded_ids(session) -> set[int]:
    """RAG 排除集:rag_status 非 indexed 的文档 id(语义检索/上下文不召回)."""
    result = await session.execute(
        select(Document.id).where(Document.rag_status != "indexed")
    )
    return {row[0] for row in result.all()}


def _snippet(content: str | None, q: str, width: int = 160) -> str:
    """命中位置附近的正文摘录(无命中取首部);用于降级检索的 chunk 字段."""
    if not content:
        return ""
    idx = content.lower().find(q.lower())
    if idx < 0:
        return content[:width]
    start = max(0, idx - width // 3)
    return content[start:start + width]


async def _keyword_fallback(
    session: AsyncSession, q: str, limit: int, node_id: str | None
) -> list[dict]:
    """向量化关闭时的降级检索:文档表关键词匹配,返回与语义检索同形的结果项."""
    pattern = f"%{q}%"
    stmt = select(Document).where(
        or_(
            Document.title.ilike(pattern),
            Document.path.ilike(pattern),
            Document.content.ilike(pattern),
        )
    )
    if node_id:
        stmt = stmt.where(Document.node_id == node_id)
    stmt = stmt.order_by(
        Document.title.ilike(pattern).desc(),
        Document.updated_at.desc(),
    ).limit(limit)
    docs = (await session.execute(stmt)).scalars().all()

    needle = q.lower()
    results = []
    for doc in docs:
        # 命中位置权重:标题 > 路径 > 正文(与关键词检索的排序口径一致)
        if doc.title and needle in doc.title.lower():
            score = 1.0
        elif doc.path and needle in doc.path.lower():
            score = 0.8
        else:
            score = 0.5
        results.append({
            "doc_id": doc.id,
            "title": doc.title,
            "path": doc.path,
            "node_id": doc.node_id,
            "chunk": _snippet(doc.content, q),
            "score": score,
        })
    return results


@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=1, description="查询文本"),
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    node_id: str | None = Query(None, description="节点 ID 过滤"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """语义搜索.

    使用混合检索（dense 向量 ⊕ sparse 关键词，RRF 融合）搜索相关分块;
    仅召回 rag_status 为 indexed 的文档。向量化关闭时降级为关键词检索,
    响应 ``mode`` 为 ``keyword``。
    """
    try:
        if not await _vectorization_enabled(session):
            results = await _keyword_fallback(session, q, limit, node_id)
            return {
                "query": q,
                "count": len(results),
                "mode": "keyword",
                "results": results,
            }

        excluded = await _excluded_ids(session)
        results = vector_store.search_hybrid(
            query=q,
            limit=limit,
            node_id=node_id,
            excluded_doc_ids=excluded,
        )

        return {
            "query": q,
            "count": len(results),
            "mode": "semantic",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return {
            "query": q,
            "count": 0,
            "results": [],
            "error": str(e),
        }


@router.get("/context")
async def get_rag_context(
    q: str = Query(..., min_length=1, description="查询文本"),
    limit: int = Query(3, ge=1, le=10, description="返回文档数量"),
    node_id: str | None = Query(None, description="节点 ID 过滤"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取 RAG 上下文.

    返回语义相关的文档完整内容，用于注入到 AI prompt。
    向量化关闭时降级为关键词检索,响应 ``mode`` 为 ``keyword``。
    """
    try:
        enabled = await _vectorization_enabled(session)
        # 混合检索（可能同一文档命中多个 chunk）
        # 为凑满 limit 个不同文档，多取候选再按 doc_id 去重
        fetch_limit = limit * settings.search_chunks_per_doc

        if enabled:
            excluded = await _excluded_ids(session)
            search_results = vector_store.search_hybrid(
                query=q,
                limit=fetch_limit,
                node_id=node_id,
                excluded_doc_ids=excluded,
            )
            mode = "semantic"
        else:
            search_results = await _keyword_fallback(session, q, fetch_limit, node_id)
            mode = "keyword"

        if not search_results:
            return {
                "query": q,
                "count": 0,
                "mode": mode,
                "documents": [],
            }

        # 按 doc_id 去重，保留分数最高的 chunk（结果已按分数降序）
        best_by_doc: dict[int, dict] = {}
        for r in search_results:
            doc_id = r["doc_id"]
            if doc_id not in best_by_doc or r["score"] > best_by_doc[doc_id]["score"]:
                best_by_doc[doc_id] = r
        ordered = list(best_by_doc.values())[:limit]

        # 获取文档完整内容
        doc_ids = [r["doc_id"] for r in ordered]
        stmt = select(Document).where(Document.id.in_(doc_ids))
        result = await session.execute(stmt)
        documents = {doc.id: doc for doc in result.scalars().all()}

        # 按搜索结果顺序组装
        context_docs = []
        for search_result in ordered:
            doc_id = search_result["doc_id"]
            doc = documents.get(doc_id)
            if doc:
                context_docs.append({
                    "title": doc.title,
                    "content": doc.content,
                    "path": doc.path,
                    "node_id": doc.node_id,
                    "score": search_result["score"],
                    "matched_chunk": search_result["chunk"],
                })

        return {
            "query": q,
            "count": len(context_docs),
            "mode": mode,
            "documents": context_docs,
        }

    except Exception as e:
        logger.error(f"RAG context error: {e}")
        return {
            "query": q,
            "count": 0,
            "documents": [],
            "error": str(e),
        }


@router.post("/index")
async def index_documents(
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """全量向量化所有非 excluded 文档(手动向量化的批量入口,admin).

    向量化关闭时返回 409。开启时把非 excluded 且有内容的文档(含
    not_indexed/pending)排队进入后台统一通道,完成后回写 indexed;
    嵌入不阻塞响应,单篇失败仅告警。响应只报排队数——分块总数请查
    `GET /api/rag/stats`(此处不查向量库,避免请求被远程库连接拖住)。
    """
    from app.services.rag.sync import collect_backfill_payload, sync_index_and_mark

    try:
        if not await _vectorization_enabled(session):
            raise HTTPException(status_code=409, detail=VECTORIZATION_DISABLED_DETAIL)

        payload = await collect_backfill_payload(session)
        if payload:
            background_tasks.add_task(sync_index_and_mark, payload, [])

        return {
            "message": f"Indexing {len(payload)} documents in background",
            "queued": len(payload),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Index error: {e}")
        return {
            "message": f"Index failed: {e}",
            "queued": 0,
        }


@router.get("/stats")
async def get_vector_stats(
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取向量存储统计与向量化开关状态(关闭时不连接向量库)."""
    if not await _vectorization_enabled(session):
        return {"total_chunks": 0, "vectorization_enabled": False}

    try:
        # psycopg2 为同步驱动,放入线程池避免阻塞事件循环
        stats = await asyncio.to_thread(vector_store.get_stats)
        return {**stats, "vectorization_enabled": True}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"total_chunks": 0, "vectorization_enabled": True, "error": str(e)}
