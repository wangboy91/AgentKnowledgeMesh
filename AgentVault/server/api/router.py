"""API 路由汇总."""

from fastapi import APIRouter

from api.documents import router as documents_router
from api.search import router as search_router
from api.nodes import router as nodes_router
from api.context import router as context_router

router = APIRouter()

router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(search_router, prefix="/search", tags=["search"])
router.include_router(nodes_router, prefix="/nodes", tags=["nodes"])
router.include_router(context_router, prefix="/context", tags=["context"])


@router.get("/stats")
async def get_stats():
    """获取系统统计信息."""
    from sqlalchemy import select, func
    from db import async_session
    from models.document import Document
    from models.node import Node
    from services.websocket import manager

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
