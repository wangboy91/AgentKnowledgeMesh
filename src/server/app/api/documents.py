"""文档 API.

提供文档列表、详情、扫描等接口。
"""

import hashlib
from pathlib import Path
from pydantic import BaseModel

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.document import Document
from app.config import settings
from app.services.auth import require_auth

router = APIRouter()


class DocumentUpdate(BaseModel):
    content: str


class DocumentCreate(BaseModel):
    path: str
    title: str
    content: str


class DocumentRagUpdate(BaseModel):
    enabled: bool  # True=加入 RAG,False=移出


class DocumentRagBatch(BaseModel):
    doc_ids: list[int]
    enabled: bool


@router.get("")
async def list_documents(
    node_id: str | None = Query(None, description="节点 ID 过滤(缺省全量;local 为 hub 本机目录)"),
    rag_status: str | None = Query(None, description="按 RAG 状态过滤(indexed/pending/excluded)"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取文档列表（不含内容），可按 node_id / rag_status 过滤."""
    stmt = select(Document).order_by(Document.updated_at.desc())
    if node_id:
        stmt = stmt.where(Document.node_id == node_id)
    if rag_status:
        stmt = stmt.where(Document.rag_status == rag_status)
    result = await session.execute(stmt)
    documents = result.scalars().all()
    return [doc.to_dict(include_content=False) for doc in documents]


@router.get("/tree")
async def get_document_tree(
    node_id: str | None = Query(None, description="节点 ID 过滤(缺省全量)"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取文件树结构(可指定节点;文件节点携带 rag_status 信息)."""
    stmt = select(Document.path, Document.title, Document.rag_status)
    if node_id:
        stmt = stmt.where(Document.node_id == node_id)
    result = await session.execute(stmt)
    rows = result.all()

    tree = {}
    for path, title, rag_status in rows:
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = {
                    "_title": title,
                    "_path": path,
                    "_rag_status": rag_status,
                }
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    return tree


@router.get("/{doc_id}")
async def get_document(
    doc_id: int,
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取文档详情（含内容）."""
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.to_dict(include_content=True)


@router.post("/scan")
async def scan_documents(
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """触发扫描知识库目录(RAG 模式联动:auto 后台向量化 created/updated 并清除非现向量)."""
    from app.services.scanner import scan_knowledge_root
    from app.services.indexer import sync_documents
    from app.services.rag.sync import get_rag_mode, sync_index_and_mark

    scanned = await scan_knowledge_root()
    rag_mode = await get_rag_mode(session)
    stats = await sync_documents(session, scanned, rag_mode=rag_mode)
    vector_ops = stats.pop("vector_ops", {"upserts": [], "deleted_ids": []})

    # auto 模式:返回统计后后台向量化(失败仅告警);manual 模式无任何向量操作
    if vector_ops["upserts"] or vector_ops["deleted_ids"]:
        background_tasks.add_task(
            sync_index_and_mark, vector_ops["upserts"], vector_ops["deleted_ids"]
        )

    return {
        "message": "Scan completed",
        **stats,
    }


@router.put("/{doc_id}")
async def update_document(
    doc_id: int,
    update: DocumentUpdate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
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

    # 按 RAG 模式设定状态:auto 入向量/manual 排除
    from app.services.rag.sync import get_rag_mode, sync_index_and_mark

    rag_mode = await get_rag_mode(session)
    doc.rag_status = "indexed" if rag_mode == "auto" else "excluded"
    await session.commit()

    # 向量索引(auto:后台统一通道,失败仅告警不影响主流程;manual:无向量操作)
    if rag_mode == "auto":
        background_tasks.add_task(sync_index_and_mark, [
            {
                "doc_id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "content": doc.content,
                "node_id": doc.node_id,
            }
        ], [])

    return doc.to_dict(include_content=True)


@router.post("")
async def create_document(
    create: DocumentCreate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
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
    # 按 RAG 模式设定状态:auto 入向量/manual 排除
    from app.services.rag.sync import get_rag_mode, sync_index_and_mark

    rag_mode = await get_rag_mode(session)
    doc.rag_status = "indexed" if rag_mode == "auto" else "excluded"
    await session.commit()

    # 向量索引(auto:后台统一通道,失败仅告警不影响主流程;manual:无向量操作)
    if rag_mode == "auto":
        background_tasks.add_task(sync_index_and_mark, [
            {
                "doc_id": doc.id,
                "title": doc.title,
                "path": doc.path,
                "content": doc.content,
                "node_id": doc.node_id,
            }
        ], [])

    return doc.to_dict(include_content=True)


def _upsert_payload(doc: Document, pending: bool = False) -> dict:
    """构造后台索引载荷(勾选流程用)."""
    return {
        "doc_id": doc.id,
        "title": doc.title,
        "path": doc.path,
        "content": doc.content,
        "node_id": doc.node_id,
        "pending": pending,
    }


def _rag_upserts(docs, pending: bool = False) -> list[dict]:
    """仅对有内容的文档生成索引载荷."""
    return [_upsert_payload(d, pending) for d in docs if d.content]


@router.put("/{doc_id}/rag")
async def set_document_rag(
    doc_id: int,
    body: DocumentRagUpdate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """加入/移出 RAG(admin).加入 → pending → 后台向量化 → indexed;移出 → excluded+删向量."""
    from app.services.rag.sync import sync_index_and_mark

    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if body.enabled:
        if doc.rag_status != "indexed":
            doc.rag_status = "pending"
            await session.commit()
            if doc.content:
                background_tasks.add_task(
                    sync_index_and_mark, [_upsert_payload(doc, pending=True)], []
                )
    else:
        doc.rag_status = "excluded"
        await session.commit()
        background_tasks.add_task(sync_index_and_mark, [], [doc.id])

    await session.refresh(doc)
    return doc.to_dict()


@router.post("/rag/batch")
async def batch_set_rag(
    body: DocumentRagBatch,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """批量加入/移出 RAG(admin)."""
    from app.services.rag.sync import sync_index_and_mark

    result = await session.execute(
        select(Document).where(Document.id.in_(body.doc_ids))
    )
    docs = result.scalars().all()

    enqueue_pending, enqueue_delete = [], []
    for doc in docs:
        if body.enabled:
            if doc.rag_status != "indexed":
                doc.rag_status = "pending"
                if doc.content:
                    enqueue_pending.append(_upsert_payload(doc, pending=True))
        else:
            doc.rag_status = "excluded"
            enqueue_delete.append(doc.id)
    await session.commit()

    if enqueue_pending:
        background_tasks.add_task(sync_index_and_mark, enqueue_pending, [])
    if enqueue_delete:
        background_tasks.add_task(sync_index_and_mark, [], enqueue_delete)

    return {"updated": len(docs)}
