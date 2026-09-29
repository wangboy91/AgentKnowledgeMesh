"""文档扫描与同步(hash-first 增量).

负责：
1. 扫描本地知识库
2. 与本地同步快照 diff 分类后推送:新增/变更带全文,未变只报 path+hash,消失进 deletions
3. 仅在 Hub 确认成功(200)后更新快照;失败不动快照,下轮自动重试
4. 响应 Hub 的文档内容请求
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from akm_shared.scanner import (
    DEFAULT_MAX_SIZE_BYTES,
    ScannedDocument,
    scan_knowledge_roots,
    scan_one,
)

from app.config import NodeSettings
import app.state as state
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
        self.snapshot_path = (
            snapshot_path if snapshot_path is not None else state.DEFAULT_SNAPSHOT_PATH
        )
        # 并发保护(add-node-file-watch):监听 / 定时对账 / Hub 的 sync_request
        # 可能同时触发,串行化以免重复上传。正确性由"快照仅在 200 后更新"保证,
        # 这里只为省流量。
        self._lock = asyncio.Lock()

    async def sync_documents(self):
        """扫描并按 hash-first 差异同步文档到 Hub(全量).

        并发保护见 `_lock` 注释;全量同步由"扫描结果 vs 快照"推导删除,
        因此调用方不必传删除列表。
        """
        async with self._lock:
            await self._sync_documents()

    async def _sync_documents(self):
        """全量同步实现(调用方须已持有 self._lock)."""
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

    async def sync_paths(
        self,
        changed: list[Path] | None = None,
        deleted: list[Path] | None = None,
    ) -> None:
        """局部同步:只处理本轮变更与删除的路径(add-node-file-watch).

        与全量同步的**核心区别**:不得由"未出现在本轮扫描结果中"推导删除。
        局部同步只认显式传入的 `deleted` 列表——快照中存在但本轮未扫描到的
        其他路径不代表被删除,否则会误删其他文件。

        `changed` / `deleted` 为绝对路径;不属于任何知识根、或判定不通过的
        条目被静默忽略(由定时对账兜底)。
        """
        changed = changed or []
        deleted = deleted or []
        if not changed and not deleted:
            return

        async with self._lock:
            await self._sync_paths(changed, deleted)

    async def _sync_paths(self, changed: list[Path], deleted: list[Path]) -> None:
        """局部同步实现(调用方须已持有 self._lock)."""
        if not self.transport.token:
            print("⚠️ No token available, skipping document upload")
            return

        snapshot = load_snapshot(self.snapshot_path)
        full_docs: list[ScannedDocument] = []
        hash_only: list[ScannedDocument] = []

        for path in changed:
            located = self._locate(path)
            if located is None:
                continue
            root, prefix = located
            doc = scan_one(
                path, root, prefix=prefix, max_size_bytes=DEFAULT_MAX_SIZE_BYTES
            )
            if doc is None:
                # 判定不通过 / 读取失败 / 防抖窗口内又被删除:交给定时对账兜底
                continue
            if snapshot.get(doc.path) == doc.hash:
                hash_only.append(doc)
            else:
                full_docs.append(doc)

        deletion_paths: list[str] = []
        for path in deleted:
            located = self._locate(path)
            if located is None:
                continue
            root, prefix = located
            relative = path.relative_to(root).as_posix()
            deletion_paths.append(f"{prefix}/{relative}" if prefix else relative)

        diff = SyncDiff(
            full_docs=full_docs,
            hash_only=hash_only,
            deletions=sorted(set(deletion_paths)),
        )
        if not diff.full_docs and not diff.hash_only and not diff.deletions:
            # 变更全部被判定过滤(排除目录 / 不在知识根 / 读取失败),不发空请求
            return

        print(
            f"📤 Local sync: {len(full_docs)} full-text, "
            f"{len(hash_only)} hash-only, {len(diff.deletions)} deletions"
        )

        try:
            resp = await self._upload(build_payload(diff))
        except Exception as e:
            # 网络失败:快照不动,等待下次触发重试
            print(f"⚠️ Document upload failed: {e}")
            return

        if resp.status_code != 200:
            print(f"⚠️ Document upload rejected ({resp.status_code}): {resp.text}")
            return

        stats = resp.json()
        rejected_paths = {r.get("path") for r in stats.get("rejected", [])}

        # 局部更新快照:只动本轮涉及的路径,绝不重建整个快照——否则未涉及的
        # 文件会从快照中消失,下一轮全量对账把它们当新增重传
        next_snapshot = dict(snapshot)
        for doc in full_docs + hash_only:
            if doc.path in rejected_paths:
                continue
            next_snapshot[doc.path] = doc.hash
        for relative in diff.deletions:
            next_snapshot.pop(relative, None)
        save_snapshot(next_snapshot, self.snapshot_path)

        # 保持 self.documents 与磁盘一致(供 Hub 的 doc_request 回传使用)
        by_path = {d.path: d for d in self.documents}
        for doc in full_docs + hash_only:
            by_path[doc.path] = doc
        for relative in diff.deletions:
            by_path.pop(relative, None)
        self.documents = list(by_path.values())

        print(
            f"📤 Local synced: created={stats.get('created', 0)} "
            f"updated={stats.get('updated', 0)} deleted={stats.get('deleted', 0)} "
            f"rejected={len(rejected_paths)}"
        )

    def _locate(self, path: Path) -> tuple[Path, str] | None:
        """定位绝对路径所属的知识根,返回 (root, 多根前缀).

        不在任何已配置知识根之下时返回 None。前缀规则与
        `scan_knowledge_roots` 保持一致(单根不加前缀,多根以目录名为前缀)。
        """
        roots = self.settings.knowledge_paths
        multi = len(roots) > 1
        for root in roots:
            try:
                path.relative_to(root)
            except ValueError:
                continue
            return root, (root.name if multi else "")
        return None

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
