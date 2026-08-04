"""Hub WebSocket 客户端.

负责：
1. 连接 Hub 并注册
2. 发送心跳
3. 响应文档请求
4. 发送文档更新通知
"""

import asyncio
import json
from datetime import datetime
from typing import Optional
import websockets
from websockets.exceptions import ConnectionClosed

from config import settings
from scanner import scan_knowledge_roots, ScannedDocument


class HubClient:
    """Hub WebSocket 客户端."""

    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.node_id = settings.get_node_id()
        self.node_name = settings.get_node_name()
        self.platform = settings.get_platform()
        self.connected = False
        self.documents: list[ScannedDocument] = []

    async def connect(self):
        """连接到 Hub."""
        print(f"🔗 Connecting to Hub: {settings.hub_url}")

        try:
            self.ws = await websockets.connect(settings.hub_url)
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

    async def handle_messages(self):
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
                    await self.sync_documents()

                elif msg_type == "doc_request":
                    # Hub 请求特定文档内容
                    path = data.get("path")
                    await self.send_doc_content(path)

        except ConnectionClosed:
            self.connected = False
            print("❌ Connection lost")

    async def sync_documents(self):
        """扫描并同步文档到 Hub."""
        print("📄 Scanning documents...")
        roots = settings.knowledge_paths
        self.documents = scan_knowledge_roots(roots)
        print(f"📄 Found {len(self.documents)} documents")

        # 通过 HTTP API 同步文档列表
        # TODO: 实现 HTTP 同步
        # 现在先打印文档列表
        for doc in self.documents[:5]:
            print(f"  - {doc.path}: {doc.title}")

    async def send_doc_content(self, path: str):
        """发送文档内容到 Hub."""
        doc = next((d for d in self.documents if d.path == path), None)
        if not doc:
            return

        if self.ws:
            await self.ws.send(json.dumps({
                "type": "doc_response",
                "node_id": self.node_id,
                "path": path,
                "content": doc.content,
                "title": doc.title,
                "hash": doc.hash,
                "size": doc.size,
            }))

    async def run(self):
        """运行客户端主循环."""
        while True:
            try:
                if await self.connect():
                    # 启动心跳任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    # 启动消息处理
                    message_task = asyncio.create_task(self.handle_messages())

                    # 初始同步
                    await self.sync_documents()

                    # 等待任一任务完成
                    done, pending = await asyncio.wait(
                        [heartbeat_task, message_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 取消剩余任务
                    for task in pending:
                        task.cancel()

                # 断线重连
                print("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(5)

    async def _heartbeat_loop(self):
        """心跳循环."""
        while self.connected:
            await self.send_heartbeat()
            await asyncio.sleep(settings.heartbeat_interval)
