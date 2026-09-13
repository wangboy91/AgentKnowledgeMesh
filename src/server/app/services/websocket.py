"""WebSocket 服务.

Hub 作为 WebSocket Server，接收 Node 连接，处理：
1. 节点注册
2. 心跳维护
3. 文档同步
4. 文档请求代理
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from app.db import async_session
from app.models.node import Node


class ConnectionManager:
    """WebSocket 连接管理器."""

    def __init__(self):
        # node_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # WebSocket -> node_id
        self.connection_nodes: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, node_id: str):
        """登记连接（accept 由 websocket_endpoint 统一执行，避免二次 accept）."""
        self.active_connections[node_id] = websocket
        self.connection_nodes[websocket] = node_id
        print(f"✅ Node connected: {node_id}")

    def disconnect(self, websocket: WebSocket):
        """断开连接."""
        node_id = self.connection_nodes.pop(websocket, None)
        if node_id:
            self.active_connections.pop(node_id, None)
            print(f"❌ Node disconnected: {node_id}")

    async def send_to_node(self, node_id: str, message: dict):
        """发送消息到指定节点."""
        websocket = self.active_connections.get(node_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """广播消息到所有节点."""
        for websocket in self.active_connections.values():
            await websocket.send_json(message)

    def get_online_nodes(self) -> list[str]:
        """获取在线节点ID列表."""
        return list(self.active_connections.keys())

    def is_online(self, node_id: str) -> bool:
        """检查节点是否在线."""
        return node_id in self.active_connections


# 全局连接管理器
manager = ConnectionManager()


async def handle_node_message(websocket: WebSocket, message: dict) -> Optional[dict]:
    """处理节点消息.

    消息类型：
    - register: 节点注册
    - heartbeat: 心跳
    - doc_update: 文档更新通知
    - doc_response: 文档内容响应
    """
    msg_type = message.get("type")

    if msg_type == "register":
        return await handle_register(websocket, message)

    elif msg_type == "heartbeat":
        return await handle_heartbeat(message)

    elif msg_type == "doc_update":
        return await handle_doc_update(message)

    elif msg_type == "doc_response":
        # 转发给请求者（如果有）
        return None

    return {"type": "error", "message": f"Unknown message type: {msg_type}"}


async def handle_register(websocket: WebSocket, message: dict) -> dict:
    """处理节点注册."""
    node_id = message.get("node_id")
    name = message.get("name", "Unknown")
    platform = message.get("platform", "unknown")
    token = message.get("token")

    if not node_id:
        return {"type": "error", "message": "Missing node_id"}

    # 节点凭证校验:必须携带 token、节点已存在(经 akm-node login 创建)、
    # token 与记录一致且节点未被禁用;失败返回 error,端点将以 4001 关闭连接
    if not token:
        return {"type": "error", "message": "Missing node token (run 'akm-node login' first)"}

    async with async_session() as session:
        result = await session.execute(select(Node).where(Node.id == node_id))
        node = result.scalar_one_or_none()

        if node is None or node.token != token or node.disabled:
            return {"type": "error", "message": "Invalid node credentials"}

        node.name = name
        node.platform = platform
        node.status = "online"
        node.last_heartbeat = datetime.utcnow()
        await session.commit()

    # 注册到连接管理器
    await manager.connect(websocket, node_id)

    return {"type": "register_ack", "node_id": node_id, "status": "ok", "token": node.token}


async def handle_heartbeat(message: dict) -> dict:
    """处理心跳."""
    node_id = message.get("node_id")
    if not node_id:
        return {"type": "error", "message": "Missing node_id"}

    async with async_session() as session:
        result = await session.execute(select(Node).where(Node.id == node_id))
        node = result.scalar_one_or_none()
        if node:
            node.last_heartbeat = datetime.utcnow()
            node.status = "online"
            await session.commit()

    return {"type": "heartbeat_ack"}


async def handle_doc_update(message: dict) -> dict:
    """处理文档更新通知."""
    # 这里只是通知，实际文档内容通过 HTTP API 同步
    node_id = message.get("node_id")
    path = message.get("path")
    action = message.get("action")  # create/update/delete

    print(f"📄 Doc update from {node_id}: {action} {path}")

    return {"type": "doc_update_ack"}


async def handle_node_disconnect(node_id: str):
    """处理节点断开连接."""
    async with async_session() as session:
        result = await session.execute(select(Node).where(Node.id == node_id))
        node = result.scalar_one_or_none()
        if node:
            node.status = "offline"
            await session.commit()


async def reset_all_nodes_offline() -> None:
    """Hub 启动时重置全部节点为离线.

    进程内不存在任何活跃连接;若上次进程被强杀,断线清理未执行,
    DB 中会残留 status='online' 的陈旧记录,在此统一纠正。
    """
    async with async_session() as session:
        result = await session.execute(select(Node).where(Node.status == "online"))
        nodes = result.scalars().all()
        for node in nodes:
            node.status = "offline"
        await session.commit()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点."""
    node_id = None
    try:
        # Starlette 要求先 accept 才能收发消息，否则 receive_json 会抛
        # RuntimeError('WebSocket is not connected...')，导致握手被拒(500)
        await websocket.accept()

        # 等待注册消息
        data = await websocket.receive_json()
        response = await handle_node_message(websocket, data)

        if response:
            await websocket.send_json(response)

        node_id = manager.connection_nodes.get(websocket)

        if not node_id:
            await websocket.close(code=4001, reason="Registration failed")
            return

        # 消息循环
        while True:
            data = await websocket.receive_json()
            response = await handle_node_message(websocket, data)
            if response:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        if node_id:
            await handle_node_disconnect(node_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        if node_id:
            await handle_node_disconnect(node_id)
