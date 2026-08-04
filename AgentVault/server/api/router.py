"""API 路由汇总."""

from fastapi import APIRouter

from api.documents import router as documents_router
from api.search import router as search_router

router = APIRouter()

router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(search_router, prefix="/search", tags=["search"])


@router.get("/stats")
async def get_stats():
    """获取系统统计信息."""
    from sqlalchemy import select, func
    from db import async_session
    from models.document import Document

    async with async_session() as session:
        total = await session.scalar(select(func.count(Document.id)))
        total_size = await session.scalar(select(func.sum(Document.size)))

    return {
        "total_documents": total or 0,
        "total_size_bytes": total_size or 0,
    }
