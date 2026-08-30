"""RAG API.

提供语义搜索和 RAG 上下文组装功能。
"""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.document import Document
from app.services.rag import vector_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=1, description="查询文本"),
    limit: int = Query(5, ge=1, le=20, description="返回数量"),
    node_id: str | None = Query(None, description="节点 ID 过滤"),
):
    """语义搜索.

    使用混合检索（dense 向量 ⊕ sparse 关键词，RRF 融合）搜索相关分块。
    """
    try:
        results = vector_store.search_hybrid(
            query=q,
            limit=limit,
            node_id=node_id,
        )

        return {
            "query": q,
            "count": len(results),
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
    session: AsyncSession = Depends(get_session),
):
    """获取 RAG 上下文.

    返回语义相关的文档完整内容，用于注入到 AI prompt。
    """
    try:
        # 混合检索（可能同一文档命中多个 chunk）
        # 为凑满 limit 个不同文档，多取候选再按 doc_id 去重
        fetch_limit = limit * settings.search_chunks_per_doc
        search_results = vector_store.search_hybrid(
            query=q,
            limit=fetch_limit,
            node_id=node_id,
        )

        if not search_results:
            return {
                "query": q,
                "count": 0,
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
    session: AsyncSession = Depends(get_session),
):
    """索引所有文档到向量存储.

    扫描数据库中的所有文档，生成向量并存储。
    """
    try:
        # 获取所有文档
        stmt = select(Document)
        result = await session.execute(stmt)
        documents = result.scalars().all()

        indexed = 0
        for doc in documents:
            if doc.content:
                vector_store.add_document(
                    doc_id=doc.id,
                    title=doc.title,
                    path=doc.path,
                    content=doc.content,
                    node_id=doc.node_id,
                )
                indexed += 1

        stats = vector_store.get_stats()

        return {
            "message": f"Indexed {indexed} documents",
            "indexed": indexed,
            "total_chunks": stats["total_chunks"],
        }

    except Exception as e:
        logger.error(f"Index error: {e}")
        return {
            "message": f"Index failed: {e}",
            "indexed": 0,
        }


@router.get("/stats")
async def get_vector_stats():
    """获取向量存储统计."""
    try:
        stats = vector_store.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"total_chunks": 0, "error": str(e)}
