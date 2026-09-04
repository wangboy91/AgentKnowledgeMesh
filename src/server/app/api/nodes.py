"""节点管理 API.

提供节点列表、详情、文档等接口。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.node import Node
from app.models.document import Document
from app.services.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter()


class NodeDocumentItem(BaseModel):
    """节点推送的单篇文档."""

    path: str
    title: str
    hash: str
    size: int
    content: str


class NodeDocumentsPayload(BaseModel):
    """节点文档上传请求体."""

    documents: list[NodeDocumentItem]


@router.get("")
async def list_nodes(
    session: AsyncSession = Depends(get_session),
):
    """获取所有节点列表."""
    result = await session.execute(select(Node).order_by(Node.created_at.desc()))
    nodes = result.scalars().all()

    # 更新在线状态
    online_nodes = manager.get_online_nodes()
    for node in nodes:
        if node.id in online_nodes:
            node.status = "online"

    return [node.to_dict() for node in nodes]


@router.get("/{node_id}")
async def get_node(
    node_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取节点详情."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 更新在线状态
    node.status = "online" if manager.is_online(node_id) else "offline"

    return node.to_dict()


@router.get("/{node_id}/documents")
async def get_node_documents(
    node_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取节点的文档列表."""
    # 检查节点是否存在
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 获取该节点的文档
    result = await session.execute(
        select(Document)
        .where(Document.node_id == node_id)
        .order_by(Document.updated_at.desc())
    )
    documents = result.scalars().all()

    return {
        "node": node.to_dict(),
        "documents": [doc.to_dict(include_content=False) for doc in documents],
    }


def _sync_vectors(upserts: list[dict], deleted_ids: list[int]) -> None:
    """后台维护向量索引（同步函数，经 BackgroundTasks 在线程池执行）.

    逐文档降级：单篇失败仅记告警并继续，不影响其余文档与已完成的同步结果。
    """
    from app.services.rag import vector_store

    for doc in upserts:
        try:
            vector_store.add_document(
                doc_id=doc["doc_id"],
                title=doc["title"],
                path=doc["path"],
                content=doc["content"],
                node_id=doc["node_id"],
            )
        except Exception as e:
            logger.warning(f"Vector index update failed for doc {doc['doc_id']}: {e}")

    for doc_id in deleted_ids:
        try:
            vector_store.delete_document(doc_id)
        except Exception as e:
            logger.warning(f"Vector index cleanup failed for doc {doc_id}: {e}")


async def _sync_node_documents(
    session: AsyncSession,
    node_id: str,
    documents: list[NodeDocumentItem],
) -> tuple[dict, dict]:
    """按 (node_id, path) 作用域增量同步文档.

    只增删改 node_id 匹配的文档，绝不触及 local 或其他节点的文档。
    返回 (同步统计, 向量操作载荷)；载荷在 commit 前捕获所需数据
    （新增文档 flush 取 id、待删文档删除前取 id），供响应后派发后台向量维护。
    """
    result = await session.execute(
        select(Document).where(Document.node_id == node_id)
    )
    existing = {doc.path: doc for doc in result.scalars().all()}

    scanned_paths = {doc.path for doc in documents}
    stats = {"created": 0, "updated": 0, "deleted": 0}
    changed: list[Document] = []

    for doc in documents:
        old_doc = existing.get(doc.path)
        if old_doc is None:
            new_doc = Document(
                node_id=node_id,
                path=doc.path,
                title=doc.title,
                hash=doc.hash,
                size=doc.size,
                content=doc.content,
            )
            session.add(new_doc)
            stats["created"] += 1
            changed.append(new_doc)
        elif old_doc.hash != doc.hash:
            old_doc.title = doc.title
            old_doc.hash = doc.hash
            old_doc.size = doc.size
            old_doc.content = doc.content
            stats["updated"] += 1
            changed.append(old_doc)

    deleted_ids: list[int] = []
    missing = set(existing.keys()) - scanned_paths
    if missing:
        # bulk delete 前捕获 doc_id（删除后无从查询，向量分块按 doc_id 清理）
        deleted_ids = [existing[p].id for p in missing]
        await session.execute(
            delete(Document).where(
                Document.node_id == node_id,
                Document.path.in_(missing),
            )
        )
        stats["deleted"] = len(missing)

    # flush 使新增文档获得 id，载荷在 commit 前构建（避免回滚后向量已派发）
    await session.flush()
    upserts = [
        {
            "doc_id": d.id,
            "title": d.title,
            "path": d.path,
            "content": d.content,
            "node_id": d.node_id,
        }
        for d in changed
    ]
    await session.commit()
    return stats, {"upserts": upserts, "deleted_ids": deleted_ids}


@router.put("/{node_id}/documents")
async def put_node_documents(
    node_id: str,
    payload: NodeDocumentsPayload,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """接收节点推送的文档并增量入库（作用域限定为该节点）.

    入库成功后在后台维护向量索引（created/updated 嵌入、deleted 清理），
    嵌入耗时与失败均不影响本次同步响应。
    """
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 校验 Bearer token
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    if not token or token != node.token:
        raise HTTPException(status_code=401, detail="Invalid token")

    stats, vector_ops = await _sync_node_documents(session, node_id, payload.documents)

    # commit 成功后才派发后台向量维护（同步函数走线程池，不阻塞响应）
    if vector_ops["upserts"] or vector_ops["deleted_ids"]:
        background_tasks.add_task(
            _sync_vectors, vector_ops["upserts"], vector_ops["deleted_ids"]
        )

    return stats


@router.post("/{node_id}/sync")
async def sync_node_documents(
    node_id: str,
    session: AsyncSession = Depends(get_session),
):
    """请求节点同步文档.

    向在线节点发送同步请求，节点会将文档列表发送回来。
    """
    if not manager.is_online(node_id):
        raise HTTPException(status_code=400, detail="Node is offline")

    # 发送同步请求到节点
    await manager.send_to_node(node_id, {"type": "sync_request"})

    return {"message": "Sync request sent"}


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """删除节点及其所有文档（含向量分块的级联清理）."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 删除前捕获文档 id（删除后无从映射向量分块）
    result = await session.execute(
        select(Document.id).where(Document.node_id == node_id)
    )
    doc_ids = [row[0] for row in result.all()]

    # 删除该节点的所有文档
    from sqlalchemy import delete
    await session.execute(delete(Document).where(Document.node_id == node_id))

    # 删除节点
    await session.delete(node)
    await session.commit()

    # 后台级联清理该节点全部文档的向量分块（失败仅告警）
    if doc_ids:
        background_tasks.add_task(_sync_vectors, [], doc_ids)

    return {"message": "Node and its documents deleted"}
