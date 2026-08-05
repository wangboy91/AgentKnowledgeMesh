"""节点管理 API.

提供节点列表、详情、文档等接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models.node import Node
from models.document import Document
from services.websocket import manager

router = APIRouter()


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
