"""API 路由包：聚合所有子路由.

每个模块暴露一个 APIRouter，统一在此挂载前缀和标签。
"""

from fastapi import APIRouter

from app.api.context import router as context_router
from app.api.convert import router as convert_router
from app.api.documents import router as documents_router
from app.api.mcp import router as mcp_router
from app.api.nodes import router as nodes_router
from app.api.rag import router as rag_router
from app.api.search import router as search_router

router = APIRouter()

router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(search_router, prefix="/search", tags=["search"])
router.include_router(nodes_router, prefix="/nodes", tags=["nodes"])
router.include_router(context_router, prefix="/context", tags=["context"])
router.include_router(mcp_router, prefix="/mcp", tags=["mcp"])
router.include_router(rag_router, prefix="/rag", tags=["rag"])
router.include_router(convert_router, prefix="/convert", tags=["convert"])


@router.get("/stats")
async def get_stats():
    """获取系统统计信息."""
    from sqlalchemy import select, func

    from app.db import async_session
    from app.models.document import Document
    from app.models.node import Node
    from app.services.websocket import manager

    async with async_session() as session:
        total_docs = await session.scalar(select(func.count(Document.id)))
        total_size = await session.scalar(select(func.sum(Document.size)))
        total_nodes = await session.scalar(select(func.count(Node.id)))

    online_nodes = len(manager.get_online_nodes())

    return {
        "total_documents": total_docs or 0,
        "total_size_bytes": total_size or 0,
        "total_nodes": total_nodes or 0,
        "online_nodes": online_nodes,
    }
