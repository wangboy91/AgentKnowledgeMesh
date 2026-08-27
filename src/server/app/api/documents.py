"""文档 API.

提供文档列表、详情、扫描等接口。
"""

import hashlib
from pathlib import Path
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.document import Document
from app.config import settings

router = APIRouter()


class DocumentUpdate(BaseModel):
    content: str


class DocumentCreate(BaseModel):
    path: str
    title: str
    content: str


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
    from app.services.scanner import scan_knowledge_root
    from app.services.indexer import sync_documents

    documents = await scan_knowledge_root()
    stats = await sync_documents(session, documents)

    return {
        "message": "Scan completed",
        **stats,
    }


@router.put("/{doc_id}")
async def update_document(
    doc_id: int,
    update: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新文档内容."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 更新内容和 hash
    doc.content = update.content
    doc.hash = hashlib.sha256(update.content.encode("utf-8")).hexdigest()
    doc.size = len(update.content.encode("utf-8"))

    # 提取标题（如果有 # 开头的行）
    for line in update.content.split("\n")[:5]:
        line = line.strip()
        if line.startswith("# "):
            doc.title = line[2:].strip()
            break

    await session.commit()

    # 更新向量存储
    try:
        from app.services.rag.vector_store import add_document
        add_document(
            doc_id=doc.id,
            title=doc.title,
            path=doc.path,
            content=doc.content,
            node_id=doc.node_id,
        )
    except Exception:
        pass  # 向量更新失败不影响主流程

    return doc.to_dict(include_content=True)


@router.post("")
async def create_document(
    create: DocumentCreate,
    session: AsyncSession = Depends(get_session),
):
    """创建新文档."""
    # 检查路径是否已存在
    existing = await session.execute(
        select(Document).where(Document.path == create.path)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document already exists at this path")

    # 创建文档
    content_hash = hashlib.sha256(create.content.encode("utf-8")).hexdigest()

    # 如果没有标题，从内容提取
    title = create.title
    if not title:
        for line in create.content.split("\n")[:5]:
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if not title:
            title = Path(create.path).stem

    doc = Document(
        path=create.path,
        title=title,
        hash=content_hash,
        size=len(create.content.encode("utf-8")),
        content=create.content,
    )

    session.add(doc)
    await session.commit()

    # 添加到向量存储
    try:
        from app.services.rag.vector_store import add_document
        add_document(
            doc_id=doc.id,
            title=doc.title,
            path=doc.path,
            content=doc.content,
            node_id=doc.node_id,
        )
    except Exception:
        pass

    return doc.to_dict(include_content=True)
