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
        # 节点凭证(account-auth):由 `akm-node login` 写入本地配置
        self.token: Optional[str] = settings.node_token or None
        # 最近一次连接失败是否因凭证无效(供运行层决定是否提供现场重登)
        self.credential_failed = False

    async def connect(self):
        """连接到 Hub."""
        print(f"🔗 Connecting to Hub: {self.settings.hub_url}")
        self.credential_failed = False

        try:
            self.ws = await websockets.connect(self.settings.hub_url)
            self.connected = True

            # 发送注册消息(必须携带节点 token,匿名注册被拒)
            await self.ws.send(json.dumps({
                "type": "register",
                "node_id": self.node_id,
                "name": self.node_name,
                "platform": self.platform,
                "token": self.settings.node_token,
            }))

            # 等待注册确认
            response = await self.ws.recv()
            data = json.loads(response)

            if data.get("type") == "register_ack":
                self.token = data.get("token") or self.token
                print(f"✅ Registered with Hub: {self.node_id}")
                return True
            else:
                print(f"❌ Registration failed: {data}")
                msg = str(data.get("message", ""))
                if "credentials" in msg or "token" in msg or "disabled" in msg:
                    self.credential_failed = True
                    print("   提示:节点凭证无效或已失效,请重新执行 `uv run akm-node login`")
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
