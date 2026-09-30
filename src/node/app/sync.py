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
    """
    payload, _ = _build_payload_and_size(diff, include_deletions=True)
    return payload


# 单个文档条目除 content 之外的固定开销估算（字节）：
# path / title / hash / size 字段与 JSON 键名、引号、逗号等。
# 取值刻意宽裕——宁可高估导致批次偏小，也不低估而冒 413 的风险。
_ENTRY_OVERHEAD_BYTES = 256


def _doc_entry(doc, with_content: bool) -> tuple[dict, int]:
    """构造单个文档条目并返回 (entry, 估算字节数).

    体积口径：content 按 UTF-8 字节长（中文 3 字节/字符）计，叠加固定开销。
    有意不做完整 json.dumps 精确测量——那是 O(n) 重复序列化，浪费 CPU，
    而估算偏保守在方向上安全（见 design.md D3）。
    """
    entry = {
        "path": doc.path,
        "title": doc.title,
        "hash": doc.hash,
        "size": doc.size,
    }
    size = (
        _ENTRY_OVERHEAD_BYTES
        + len(doc.path.encode("utf-8"))
        + len(doc.title.encode("utf-8"))
    )
    if with_content:
        content_bytes = len(doc.content.encode("utf-8"))
        entry["content"] = doc.content
        size += content_bytes
    return entry, size


def _build_payload_and_size(diff: SyncDiff, include_deletions: bool) -> tuple[dict, int]:
    """构造 payload 并返回 (payload, 估算体积)."""
    documents = []
    total = 0
    for doc in diff.full_docs:
        entry, size = _doc_entry(doc, with_content=True)
        documents.append(entry)
        total += size
    for doc in diff.hash_only:
        entry, size = _doc_entry(doc, with_content=False)
        documents.append(entry)
        total += size
    payload: dict = {"documents": documents}
    if include_deletions:
        payload["deletions"] = diff.deletions
        total += sum(len(p.encode("utf-8")) + _ENTRY_OVERHEAD_BYTES for p in diff.deletions)
    return payload, total


def batch_payload(
    diff: SyncDiff, batch_bytes: int, batch_docs: int
) -> list[dict]:
    """把差异切分为多个 payload 批次(node-upload-batching).

    单轮推送超量时，单个请求体可能撞上对端反向代理的 body 上限（nginx 默认
    client_max_body_size 1m）而 413。切批让任意规模的知识库都能同步成功。

    规则（见 openspec/changes/2026-09-30-fix-node-upload-batching/design.md）：
    - 条数与体积两个维度任一触顶即封批；`<= 0` 表示该维度不限制
    - 单篇自身超限时**独占一批**（最小切分粒度，保证算法每轮至少推进一个条目，
      不会死循环）
    - `deletions` **仅随最后一批**；前序批次的 payload 仍携带空 `deletions` 键，
      以关闭 Hub 侧「列表缺失即删除」的隐式推导

    未触发任何上限时返回单批，且结构与本函数引入前逐字节一致。
    """
    # 保持与 build_payload 相同的顺序：先 full_docs（含全文）再 hash_only（仅元信息）
    entries: list[tuple[dict, int, str]] = []
    for doc in diff.full_docs:
        entry, size = _doc_entry(doc, with_content=True)
        entries.append((entry, size, doc.path))
    for doc in diff.hash_only:
        entry, size = _doc_entry(doc, with_content=False)
        entries.append((entry, size, doc.path))

    limit_bytes = batch_bytes if batch_bytes > 0 else None
    limit_docs = batch_docs if batch_docs > 0 else None

    batches: list[list[dict]] = []
    current: list[dict] = []
    current_bytes = 0

    for entry, size, _path in entries:
        would_exceed_docs = limit_docs is not None and len(current) >= limit_docs
        would_exceed_bytes = (
            limit_bytes is not None and current and current_bytes + size > limit_bytes
        )
        if would_exceed_docs or would_exceed_bytes:
            batches.append(current)
            current, current_bytes = [], 0
        current.append(entry)
        current_bytes += size

        # 单篇即超限：立即封批独占，避免累加到下一批时永远"超限"
        if limit_bytes is not None and current_bytes > limit_bytes:
            batches.append(current)
            current, current_bytes = [], 0

    if current:
        batches.append(current)
    if not batches:
        # 空 diff（无文档）也要发一批（携带 deletions），保持既有行为
        batches = [[]]

    # deletions 仅随最后一批；每批都带该键
    payloads: list[dict] = []
    last = len(batches) - 1
    for idx, docs in enumerate(batches):
        payload: dict = {"documents": docs}
        payload["deletions"] = diff.deletions if idx == last else []
        payloads.append(payload)
    return payloads


def merge_stats(results: list[dict]) -> dict:
    """把各批 Hub 响应的统计跨批汇总(node-upload-batching).

    created/updated/deleted 求和；rejected 列表拼接（供调用方决策快照）。
    """
    merged = {"created": 0, "updated": 0, "deleted": 0, "rejected": []}
    for stats in results:
        merged["created"] += stats.get("created", 0)
        merged["updated"] += stats.get("updated", 0)
        merged["deleted"] += stats.get("deleted", 0)
        merged["rejected"].extend(stats.get("rejected", []) or [])
    return merged



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
        n_batches = len(
            batch_payload(
                diff,
                self.settings.upload_batch_bytes,
                self.settings.upload_batch_docs,
            )
        )
        batch_note = f" in {n_batches} batches" if n_batches > 1 else ""
        print(
            f"📤 Uploading: {len(diff.full_docs)} full-text, "
            f"{len(diff.hash_only)} hash-only, {len(diff.deletions)} deletions{batch_note}"
        )

        stats, failure = await self._upload_batches(diff)
        if stats is None:
            # 任一批次失败即视为整体失败:快照不动,等待下次触发重试
            print(f"⚠️ Document upload aborted: {failure}")
            return

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

        stats, failure = await self._upload_batches(diff)
        if stats is None:
            # 任一批次失败即视为整体失败:快照不动,等待下次触发重试
            print(f"⚠️ Document upload aborted: {failure}")
            return

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
        """推送单个 payload 到 Hub 并返回响应(网络错误向上抛出)."""
        url = f"{self.settings.hub_api_url.rstrip('/')}/nodes/{self.transport.node_id}/documents"
        headers = {"Authorization": f"Bearer {self.transport.token}"}
        async with httpx.AsyncClient() as client:
            return await client.put(url, json=payload, headers=headers)

    async def _upload_batches(self, diff: "SyncDiff") -> tuple[dict | None, str]:
        """按配置上限切批并串行推送(node-upload-batching).

        返回 `(汇总统计, 失败原因)`：
        - 全部批次成功 → `(merge_stats(...), "")`
        - 任一批次失败(非 200 或网络错误) → `(None, 原因描述)`，调用方据此
          **保持快照不变**。已成功批次不回滚——重传时 Hub 按 (node_id, path)+hash
          幂等处理，不产生重复数据（见 design.md D6）。

        未触发上限时只有一个批次，行为与引入前完全一致。
        """
        batches = batch_payload(
            diff,
            self.settings.upload_batch_bytes,
            self.settings.upload_batch_docs,
        )
        results: list[dict] = []
        total = len(batches)
        for idx, payload in enumerate(batches, start=1):
            try:
                resp = await self._upload(payload)
            except Exception as e:
                return None, f"批次 {idx}/{total} 网络错误: {e}"
            if resp.status_code != 200:
                return None, f"批次 {idx}/{total} 被拒({resp.status_code}): {resp.text}"
            results.append(resp.json())
        return merge_stats(results), ""

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
