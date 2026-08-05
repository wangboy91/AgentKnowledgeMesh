"""文档 API.

提供文档列表、详情、扫描等接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models.document import Document

router = APIRouter()


@router.get("")
async def list_documents(
    session: AsyncSession = Depends(get_session),
):
    """获取文档列表（不含内容）."""
    result = await session.execute(
        select(Document).order_by(Document.updated_at.desc())
    )
    documents = result.scalars().all()
    return [doc.to_dict(include_content=False) for doc in documents]


@router.get("/tree")
async def get_document_tree(
    session: AsyncSession = Depends(get_session),
):
    """获取文件树结构."""
    result = await session.execute(select(Document.path, Document.title))
    rows = result.all()

    tree = {}
    for path, title in rows:
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = {"_title": title, "_path": path}
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    return tree


@router.get("/{doc_id}")
async def get_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
):
    """获取文档详情（含内容）."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.to_dict(include_content=True)


@router.post("/scan")
async def scan_documents(
    session: AsyncSession = Depends(get_session),
):
    """触发扫描知识库目录."""
    from services.scanner import scan_knowledge_root
    from services.indexer import sync_documents

    documents = await scan_knowledge_root()
    stats = await sync_documents(session, documents)

    return {
        "message": "Scan completed",
        **stats,
    }
