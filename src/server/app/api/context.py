"""Agent Context API.

让 AI Agent 查询知识库获取相关上下文。
返回包含完整内容的文档，便于注入到 prompt 中。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models.document import Document

router = APIRouter()


@router.get("")
async def get_context(
    q: str = Query(..., min_length=1, description="查询关键词"),
    limit: int = Query(5, ge=1, le=20, description="返回文档数量"),
    node_id: str | None = Query(None, description="指定节点ID"),
    session: AsyncSession = Depends(get_session),
):
    """获取与查询相关的文档上下文.

    返回包含完整内容的文档列表，便于 Agent 注入到 prompt。
    """
    pattern = f"%{q}%"

    # 构建查询
    query = select(Document).where(
        or_(
            Document.title.ilike(pattern),
            Document.path.ilike(pattern),
            Document.content.ilike(pattern),
        )
    )

    # 节点过滤
    if node_id:
        query = query.where(Document.node_id == node_id)

    # 标题匹配优先，限制数量
    query = query.order_by(
        Document.title.ilike(pattern).desc(),
        Document.updated_at.desc(),
    ).limit(limit)

    result = await session.execute(query)
    documents = result.scalars().all()

    # 构造 Agent 友好的返回格式
    return {
        "query": q,
        "count": len(documents),
        "documents": [
            {
                "title": doc.title,
                "content": doc.content,
                "path": doc.path,
                "node_id": doc.node_id,
            }
            for doc in documents
        ],
    }
