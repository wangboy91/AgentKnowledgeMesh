"""文档扫描与同步.

负责：
1. 扫描本地知识库
2. 同步文档到 Hub（HTTP）
3. 响应 Hub 的文档内容请求
"""

import json

import httpx

from akm_shared.scanner import (
    DEFAULT_MAX_SIZE_BYTES,
    ScannedDocument,
    scan_knowledge_roots,
)

from app.config import NodeSettings
from app.transport import HubTransport


class DocumentSync:
    """文档扫描与同步."""

    def __init__(self, transport: HubTransport, settings: NodeSettings):
        self.transport = transport
        self.settings = settings
        self.documents: list[ScannedDocument] = []

    async def sync_documents(self):
        """扫描并同步文档到 Hub."""
        print("📄 Scanning documents...")
        roots = self.settings.knowledge_paths
        self.documents = scan_knowledge_roots(roots, max_size_bytes=DEFAULT_MAX_SIZE_BYTES)
        print(f"📄 Found {len(self.documents)} documents")

        # 通过 HTTP API 同步文档列表
        if not self.transport.token:
            print("⚠️ No token available, skipping document upload")
            return

        payload = {
            "documents": [
                {
                    "path": doc.path,
                    "title": doc.title,
                    "hash": doc.hash,
                    "size": doc.size,
                    "content": doc.content,
                }
                for doc in self.documents
            ]
        }
        url = f"{self.settings.hub_api_url.rstrip('/')}/nodes/{self.transport.node_id}/documents"
        headers = {"Authorization": f"Bearer {self.transport.token}"}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.put(url, json=payload, headers=headers)
        except Exception as e:
            print(f"⚠️ Document upload failed: {e}")
            return

        if resp.status_code == 200:
            stats = resp.json()
            print(f"📤 Synced {len(self.documents)} documents: {stats}")
        else:
            # 鉴权失败(401)等情况仅记录日志，不中断连接
            print(f"⚠️ Document upload rejected ({resp.status_code}): {resp.text}")

    async def send_doc_content(self, path: str):
        """发送文档内容到 Hub."""
        doc = next((d for d in self.documents if d.path == path), None)
        if not doc:
            return

        ws = self.transport.ws
        if ws:
            await ws.send(json.dumps({
                "type": "doc_response",
                "node_id": self.transport.node_id,
                "path": path,
                "content": doc.content,
                "title": doc.title,
                "hash": doc.hash,
                "size": doc.size,
            }))
