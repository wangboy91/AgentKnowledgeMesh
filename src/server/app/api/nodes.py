"""节点管理 API.

提供节点列表、详情、文档等接口。
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.node import Node
from app.models.document import Document
from app.services.websocket import manager

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


async def _sync_node_documents(
    session: AsyncSession,
    node_id: str,
    documents: list[NodeDocumentItem],
) -> dict:
    """按 (node_id, path) 作用域增量同步文档.

    只增删改 node_id 匹配的文档，绝不触及 local 或其他节点的文档。
    """
    result = await session.execute(
        select(Document).where(Document.node_id == node_id)
    )
    existing = {doc.path: doc for doc in result.scalars().all()}

    scanned_paths = {doc.path for doc in documents}
    stats = {"created": 0, "updated": 0, "deleted": 0}

    for doc in documents:
        old_doc = existing.get(doc.path)
        if old_doc is None:
            session.add(
                Document(
                    node_id=node_id,
                    path=doc.path,
                    title=doc.title,
                    hash=doc.hash,
                    size=doc.size,
                    content=doc.content,
                )
            )
            stats["created"] += 1
        elif old_doc.hash != doc.hash:
            old_doc.title = doc.title
            old_doc.hash = doc.hash
            old_doc.size = doc.size
            old_doc.content = doc.content
            stats["updated"] += 1

    missing = set(existing.keys()) - scanned_paths
    if missing:
        await session.execute(
            delete(Document).where(
                Document.node_id == node_id,
                Document.path.in_(missing),
            )
        )
        stats["deleted"] = len(missing)

    await session.commit()
    return stats


@router.put("/{node_id}/documents")
async def put_node_documents(
    node_id: str,
    payload: NodeDocumentsPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """接收节点推送的文档并增量入库（作用域限定为该节点）."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 校验 Bearer token
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    if not token or token != node.token:
        raise HTTPException(status_code=401, detail="Invalid token")

    return await _sync_node_documents(session, node_id, payload.documents)


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
    session: AsyncSession = Depends(get_session),
):
    """删除节点及其所有文档."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 删除该节点的所有文档
    from sqlalchemy import delete
    await session.execute(delete(Document).where(Document.node_id == node_id))

    # 删除节点
    await session.delete(node)
    await session.commit()

    return {"message": "Node and its documents deleted"}
