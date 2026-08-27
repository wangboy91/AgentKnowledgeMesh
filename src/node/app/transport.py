"""Hub WebSocket 传输层.

负责：
1. 连接 Hub 并注册
2. 发送心跳
3. 响应文档请求
4. 发送文档更新通知
"""

import json
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from app.config import NodeSettings


class HubTransport:
    """Hub WebSocket 传输."""

    def __init__(self, settings: NodeSettings):
        self.settings = settings
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.node_id = settings.get_node_id()
        self.node_name = settings.get_node_name()
        self.platform = settings.get_platform()
        self.connected = False
        self.token: Optional[str] = None

    async def connect(self):
        """连接到 Hub."""
        print(f"🔗 Connecting to Hub: {self.settings.hub_url}")

        try:
            self.ws = await websockets.connect(self.settings.hub_url)
            self.connected = True

            # 发送注册消息
            await self.ws.send(json.dumps({
                "type": "register",
                "node_id": self.node_id,
                "name": self.node_name,
                "platform": self.platform,
            }))

            # 等待注册确认
            response = await self.ws.recv()
            data = json.loads(response)

            if data.get("type") == "register_ack":
                self.token = data.get("token")
                print(f"✅ Registered with Hub: {self.node_id}")
                return True
            else:
                print(f"❌ Registration failed: {data}")
                return False

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """断开连接."""
        if self.ws:
            await self.ws.close()
            self.connected = False
            print("👋 Disconnected from Hub")

    async def send_heartbeat(self):
        """发送心跳."""
        if not self.connected or not self.ws:
            return

        try:
            await self.ws.send(json.dumps({
                "type": "heartbeat",
                "node_id": self.node_id,
            }))
        except ConnectionClosed:
            self.connected = False

    async def notify_doc_update(self, path: str, action: str):
        """通知文档更新."""
        if not self.connected or not self.ws:
            return

        try:
            await self.ws.send(json.dumps({
                "type": "doc_update",
                "node_id": self.node_id,
                "path": path,
                "action": action,
            }))
        except ConnectionClosed:
            self.connected = False

    async def handle_messages(self, sync):
        """处理来自 Hub 的消息."""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "heartbeat_ack":
                    pass  # 心跳确认，忽略

                elif msg_type == "sync_request":
                    # Hub 请求同步文档
                    await sync.sync_documents()

                elif msg_type == "doc_request":
                    # Hub 请求特定文档内容
                    path = data.get("path")
                    await sync.send_doc_content(path)

        except ConnectionClosed:
            self.connected = False
            print("❌ Connection lost")
