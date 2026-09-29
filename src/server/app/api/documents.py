"""文档 API.

提供文档列表、详情、扫描等接口。
"""

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
    title: str = ""  # 缺省/为空时由写入口径从内容首行 # 或路径文件名提取
    content: str


class DocumentRagUpdate(BaseModel):
    enabled: bool  # True=加入 RAG,False=移出


class DocumentRagBatch(BaseModel):
    doc_ids: list[int]
    enabled: bool


@router.get("")
async def list_documents(
    node_id: str | None = Query(None, description="节点 ID 过滤(缺省全量;local 为 hub 本机目录)"),
    rag_status: str | None = Query(
        None, description="按 RAG 状态过滤(not_indexed/pending/indexed/excluded)"
    ),
    path: str | None = Query(None, description="按 path 精确匹配(组合 node_id 可唯一定位;供 Knowledge 页解析 doc id;非模糊匹配)"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取文档列表（不含内容），可按 node_id / rag_status / path 过滤."""
    stmt = select(Document).order_by(Document.updated_at.desc())
    if node_id:
        stmt = stmt.where(Document.node_id == node_id)
    if rag_status:
        stmt = stmt.where(Document.rag_status == rag_status)
    if path:
        stmt = stmt.where(Document.path == path)
    result = await session.execute(stmt)
    documents = result.scalars().all()
    return [doc.to_dict(include_content=False) for doc in documents]


@router.get("/tree")
async def get_document_tree(
    node_id: str | None = Query(None, description="节点 ID 过滤(缺省全量)"),
    dir: str | None = Query(None, description="目录切片:传目录路径(含空串'')返回该目录一层直接子项;缺省返回完整树"),
    principal=Depends(require_auth("viewer", allow_node=True)),
    session: AsyncSession = Depends(get_session),
):
    """获取文件树结构.

    缺省返回完整树(向后兼容);传 dir 时返回该目录的**一层直接子项**:
    文件节点 {_title,_path,_rag_status,id},目录节点 {} 占位(前端懒加载契约)。
    """
    stmt = select(Document.path, Document.title, Document.rag_status, Document.id)
    if node_id:
        stmt = stmt.where(Document.node_id == node_id)
    if dir is not None and dir != "":
        stmt = stmt.where(Document.path.startswith(dir.rstrip("/") + "/", autoescape=True))
    result = await session.execute(stmt)
    rows = result.all()

    # 切片模式:仅返回 dir 的一层直接子项
    if dir is not None:
        normalized = dir.rstrip("/")
        prefix = f"{normalized}/" if normalized else ""
        children: dict = {}
        for path, title, rag_status, doc_id in rows:
            # Python 侧二次精筛:与 SQL 侧 LIKE(部分方言大小写宽松)保持一致
            if normalized and not path.startswith(prefix):
                continue
            rest = path[len(prefix):] if prefix else path
            seg, _, tail = rest.partition("/")
            if tail:
                # 目录占位;若该名同时是文件(FS 不可达),文件分支优先覆盖
                children.setdefault(seg, {})
            else:
                children[seg] = {
                    "_title": title,
                    "_path": path,
                    "_rag_status": rag_status,
                    "id": doc_id,
                }
        return children

    tree = {}
    for path, title, rag_status, doc_id in rows:
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = {
                    "_title": title,
                    "_path": path,
                    "_rag_status": rag_status,
                    "id": doc_id,
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
    """触发扫描知识库目录(仅「向量化开启 + auto」时后台向量化 created/updated)."""
    from app.services.scanner import scan_knowledge_root
    from app.services.indexer import sync_documents
    from app.services.rag.sync import (
        get_rag_mode,
        get_vectorization_enabled,
        sync_index_and_mark,
    )

    scanned = await scan_knowledge_root()
    rag_mode = await get_rag_mode(session)
    vectorization_enabled = await get_vectorization_enabled(session)
    stats = await sync_documents(
        session,
        scanned,
        rag_mode=rag_mode,
        vectorization_enabled=vectorization_enabled,
    )
    vector_ops = stats.pop("vector_ops", {"upserts": [], "deleted_ids": []})

    # 仅「总开关开启 + auto」产生向量载荷;其余情况新文档为 not_indexed 无向量操作
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
    principal=Depends(require_auth("admin", node_write=True)),
    session: AsyncSession = Depends(get_session),
):
    """更新文档内容(admin 或节点凭证;节点仅能更新本节点名下的文档)."""
    from app.services.document_writer import update_document as _write_update
    from app.services.rag.sync import sync_index_and_mark

    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 节点凭证作用域:只能写自己名下的文档(鉴权依赖拿不到目标文档,归属判定在此)
    if principal.kind == "node" and doc.node_id != principal.node_id:
        raise HTTPException(status_code=403, detail="无权修改该文档:不属于本节点")

    doc = await _write_update(session, doc, update.content)

    # 向量索引(仅「总开关开启 + auto」且未 excluded 时 rag_status 为 indexed;后台通道,失败仅告警)
    if doc.rag_status == "indexed":
        background_tasks.add_task(sync_index_and_mark, [_upsert_payload(doc)], [])

    return doc.to_dict(include_content=True)


@router.post("")
async def create_document(
    create: DocumentCreate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin", node_write=True)),
    session: AsyncSession = Depends(get_session),
):
    """创建新文档(admin 或节点凭证).

    归属由凭证决定:节点凭证强制归属本节点(不接受请求体指定),其余归属 `local`。
    唯一性以 `(node_id, path)` 判定,同归属路径重复返回 409。
    """
    from app.services.document_writer import PathConflict
    from app.services.document_writer import create_document as _write_create
    from app.services.rag.sync import sync_index_and_mark

    node_id = principal.node_id if principal.kind == "node" else "local"

    try:
        doc = await _write_create(
            session,
            node_id=node_id,
            path=create.path,
            content=create.content,
            title=create.title,
        )
    except PathConflict:
        raise HTTPException(status_code=409, detail="Document already exists at this path")

    # 向量索引(仅「总开关开启 + auto」时 rag_status 为 indexed;后台通道,失败仅告警)
    if doc.rag_status == "indexed":
        background_tasks.add_task(sync_index_and_mark, [_upsert_payload(doc)], [])

    return doc.to_dict(include_content=True)


def _upsert_payload(doc: Document, pending: bool = False) -> dict:
    """构造后台索引载荷(单源见 services/document_writer.upsert_payload)."""
    from app.services.document_writer import upsert_payload

    return upsert_payload(doc, pending)


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
    """加入/移出 RAG(admin).加入 → pending → 后台向量化 → indexed;移出 → excluded+删向量.

    向量化总开关关闭时"加入"返回 409(无可向量化目标),"移出"仍放行(仅清理)。
    """
    from app.services.rag.sync import get_vectorization_enabled, sync_index_and_mark

    if body.enabled and not await get_vectorization_enabled(session):
        raise HTTPException(
            status_code=409,
            detail="向量化已关闭,请先在设置中开启向量化",
        )

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
    """批量加入/移出 RAG(admin).

    向量化总开关关闭时"加入"返回 409,"移出"仍放行(仅清理)。
    """
    from app.services.rag.sync import get_vectorization_enabled, sync_index_and_mark

    if body.enabled and not await get_vectorization_enabled(session):
        raise HTTPException(
            status_code=409,
            detail="向量化已关闭,请先在设置中开启向量化",
        )

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
