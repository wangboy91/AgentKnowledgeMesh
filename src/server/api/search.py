"""搜索 API.

V0.1: 基于 SQLite LIKE 的关键词搜索。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models.document import Document

router = APIRouter()


@router.get("")
async def search_documents(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    session: AsyncSession = Depends(get_session),
):
    """关键词搜索文档.

    搜索范围：标题、路径、内容。
    优先返回标题匹配的结果。
    """
    pattern = f"%{q}%"

    # 标题匹配优先
    title_match = Document.title.ilike(pattern)
    path_match = Document.path.ilike(pattern)
    content_match = Document.content.ilike(pattern)

    result = await session.execute(
        select(Document)
        .where(or_(title_match, path_match, content_match))
        .order_by(
            # 标题匹配优先排序
            title_match.desc(),
            Document.updated_at.desc(),
        )
        .limit(limit)
    )

    documents = result.scalars().all()

    return {
        "query": q,
        "count": len(documents),
        "documents": [doc.to_dict(include_content=False) for doc in documents],
    }
