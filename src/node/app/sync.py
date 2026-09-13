"""文档扫描与同步(hash-first 增量).

负责：
1. 扫描本地知识库
2. 与本地同步快照 diff 分类后推送:新增/变更带全文,未变只报 path+hash,消失进 deletions
3. 仅在 Hub 确认成功(200)后更新快照;失败不动快照,下轮自动重试
4. 响应 Hub 的文档内容请求
"""

import json
from dataclasses import dataclass, field

import httpx

from akm_shared.scanner import (
    DEFAULT_MAX_SIZE_BYTES,
    ScannedDocument,
    scan_knowledge_roots,
)

from app.config import NodeSettings
from app.state import load_snapshot, save_snapshot
from app.transport import HubTransport


@dataclass
class SyncDiff:
    """本轮扫描相对快照的差异分类."""

    full_docs: list = field(default_factory=list)   # 新增/变更:携带全文
    hash_only: list = field(default_factory=list)   # 未变更:仅报 path+hash
    deletions: list = field(default_factory=list)   # 快照有而本轮缺失:待删除


def classify_diff(documents: list, snapshot: dict) -> SyncDiff:
    """以快照为基准分类:added/changed → 含全文;unchanged → 仅 path+hash;removed → deletions."""
    diff = SyncDiff()
    scanned_paths = {doc.path for doc in documents}
    for doc in documents:
        if snapshot.get(doc.path) != doc.hash:
            diff.full_docs.append(doc)
        else:
            diff.hash_only.append(doc)
    diff.deletions = sorted(set(snapshot) - scanned_paths)
    return diff


def build_payload(diff: SyncDiff) -> dict:
    """构造上传 payload.

    deletions 键始终携带(即使为空)——它是新协议标记,Hub 据此关闭
    "列表缺失即删除"的隐式推导,避免快照与库短暂不一致时误删。
    """
    documents = [
        {
            "path": doc.path,
            "title": doc.title,
            "hash": doc.hash,
            "size": doc.size,
            "content": doc.content,
        }
        for doc in diff.full_docs
    ]
    documents.extend(
        {
            "path": doc.path,
            "title": doc.title,
            "hash": doc.hash,
            "size": doc.size,
        }
        for doc in diff.hash_only
    )
    return {"documents": documents, "deletions": diff.deletions}


class DocumentSync:
    """文档扫描与同步."""

    def __init__(
        self,
        transport: HubTransport,
        settings: NodeSettings,
        snapshot_path=None,
    ):
        self.transport = transport
        self.settings = settings
        self.documents: list[ScannedDocument] = []
        # 快照文件路径可注入(测试用),缺省 <data>/sync_state.json
        self.snapshot_path = snapshot_path

    async def sync_documents(self):
        """扫描并按 hash-first 差异同步文档到 Hub."""
        print("📄 Scanning documents...")
        roots = self.settings.knowledge_paths
        self.documents = scan_knowledge_roots(roots, max_size_bytes=DEFAULT_MAX_SIZE_BYTES)
        print(f"📄 Found {len(self.documents)} documents")

        # 通过 HTTP API 同步文档列表
        if not self.transport.token:
            print("⚠️ No token available, skipping document upload")
            return

        snapshot = load_snapshot(self.snapshot_path)
        diff = classify_diff(self.documents, snapshot)
        payload = build_payload(diff)
        print(
            f"📤 Uploading: {len(diff.full_docs)} full-text, "
            f"{len(diff.hash_only)} hash-only, {len(diff.deletions)} deletions"
        )

        try:
            resp = await self._upload(payload)
        except Exception as e:
            # 网络失败:快照不动,等待下次触发重试
            print(f"⚠️ Document upload failed: {e}")
            return

        if resp.status_code == 200:
            stats = resp.json()
            # rejected 条目视为未同步(不入快照),下轮带全文重传
            rejected_paths = {r.get("path") for r in stats.get("rejected", [])}
            if rejected_paths:
                print(
                    f"⚠️ {len(rejected_paths)} entries rejected by Hub "
                    f"(hash mismatch), will resend full text next round: "
                    f"{sorted(p for p in rejected_paths if p)}"
                )
            next_snapshot = {
                doc.path: doc.hash
                for doc in self.documents
                if doc.path not in rejected_paths
            }
            save_snapshot(next_snapshot, self.snapshot_path)
            print(
                f"📤 Synced {len(self.documents)} documents: "
                f"created={stats.get('created', 0)} updated={stats.get('updated', 0)} "
                f"deleted={stats.get('deleted', 0)} rejected={len(rejected_paths)}"
            )
        else:
            # 鉴权失败(401)等情况仅记录日志，快照不动，不中断连接
            print(f"⚠️ Document upload rejected ({resp.status_code}): {resp.text}")

    async def _upload(self, payload: dict):
        """推送 payload 到 Hub 并返回响应(网络错误向上抛出)."""
        url = f"{self.settings.hub_api_url.rstrip('/')}/nodes/{self.transport.node_id}/documents"
        headers = {"Authorization": f"Bearer {self.transport.token}"}
        async with httpx.AsyncClient() as client:
            return await client.put(url, json=payload, headers=headers)

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
