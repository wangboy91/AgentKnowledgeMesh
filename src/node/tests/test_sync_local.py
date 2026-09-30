"""局部增量同步单测（app/sync.py 的 sync_paths）.

局部同步与全量同步的**核心区别**是不得由"未扫描到"推导删除，故最关键用例是
`test_local_sync_never_deletes_unseen_paths`——一旦回归，单文件变更会误删
同节点的其他文档。
"""

import asyncio
import json

from app.config import NodeSettings
from app.sync import DocumentSync


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class _FakeTransport:
    token = "tok-1"
    node_id = "node-1"


def _ok(**over):
    body = {"created": 0, "updated": 0, "deleted": 0, "rejected": []}
    body.update(over)
    return _FakeResponse(200, body)


def _write(path, text="# T\n\nbody\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make(tmp_path, monkeypatch, responses, snapshot=None, roots=None):
    """构造 DocumentSync（tmp_path/kb 为知识根），记录上传 payload."""
    import app.sync as sync_mod

    kb = tmp_path / "kb"
    kb.mkdir(exist_ok=True)
    settings = NodeSettings(
        hub_api_url="http://test/api",
        knowledge_roots=roots if roots is not None else str(kb),
    )
    snap_path = tmp_path / "sync_state.json"
    if snapshot is not None:
        snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    sync = DocumentSync(_FakeTransport(), settings, snapshot_path=snap_path)

    calls = {"payloads": []}
    it = iter(responses)

    async def fake_upload(self, payload):
        calls["payloads"].append(payload)
        result = next(it)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(sync_mod.DocumentSync, "_upload", fake_upload)
    return sync, calls, snap_path, kb


# ---- 防误删（最关键） ----

async def test_local_sync_never_deletes_unseen_paths(tmp_path, monkeypatch):
    """局部同步不得把"快照有、本轮未扫到"的路径当删除。"""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch, [_ok(updated=1)],
        snapshot={"a.md": "old-hash", "b.md": "b-hash", "c.md": "c-hash"},
    )
    a = _write(kb / "a.md", "# A\n\nnew\n")

    await sync.sync_paths(changed=[a])

    payload = calls["payloads"][0]
    assert payload["deletions"] == []
    assert [d["path"] for d in payload["documents"]] == ["a.md"]

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert set(snap) == {"a.md", "b.md", "c.md"}
    assert snap["b.md"] == "b-hash" and snap["c.md"] == "c-hash"


async def test_local_sync_explicit_deletion(tmp_path, monkeypatch):
    """只有显式传入的 deleted 才进 deletions。"""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch, [_ok(deleted=1)],
        snapshot={"a.md": "a-hash", "b.md": "b-hash"},
    )

    await sync.sync_paths(deleted=[kb / "a.md"])  # 不创建，模拟已删除

    payload = calls["payloads"][0]
    assert payload["deletions"] == ["a.md"]
    assert payload["documents"] == []

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert set(snap) == {"b.md"}


async def test_local_sync_change_and_delete_together(tmp_path, monkeypatch):
    """同时有变更与删除：两类都生效，且不波及其他路径。"""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch, [_ok(created=1, deleted=1)],
        snapshot={"gone.md": "g-hash", "keep.md": "k-hash"},
    )
    new = _write(kb / "new.md")

    await sync.sync_paths(changed=[new], deleted=[kb / "gone.md"])

    payload = calls["payloads"][0]
    assert payload["deletions"] == ["gone.md"]
    assert [d["path"] for d in payload["documents"]] == ["new.md"]

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert set(snap) == {"new.md", "keep.md"}


# ---- 边界与语义 ----

async def test_local_sync_empty_change_set_no_upload(tmp_path, monkeypatch):
    sync, calls, _, _ = _make(tmp_path, monkeypatch, [])
    await sync.sync_paths(changed=[], deleted=[])
    assert calls["payloads"] == []


async def test_local_sync_ignores_paths_outside_roots(tmp_path, monkeypatch):
    sync, calls, _, _ = _make(tmp_path, monkeypatch, [])
    outside = _write(tmp_path / "elsewhere" / "x.md")

    await sync.sync_paths(changed=[outside])

    assert calls["payloads"] == []


async def test_local_sync_ignores_excluded_dirs(tmp_path, monkeypatch):
    sync, calls, _, kb = _make(tmp_path, monkeypatch, [])
    dep = _write(kb / "node_modules" / "x.md")

    await sync.sync_paths(changed=[dep])

    assert calls["payloads"] == []


async def test_local_sync_unchanged_reports_hash_only(tmp_path, monkeypatch):
    """监听触发但内容未变（touch）→ 仅报 hash，不含全文。"""
    from akm_shared.scanner import compute_hash

    content = "# A\n\nbody\n"
    sync, calls, _, kb = _make(
        tmp_path, monkeypatch, [_ok()],
        snapshot={"a.md": compute_hash(content)},
    )

    await sync.sync_paths(changed=[_write(kb / "a.md", content)])

    doc = calls["payloads"][0]["documents"][0]
    assert "content" not in doc
    assert doc["hash"] == compute_hash(content)


async def test_local_sync_failure_keeps_snapshot(tmp_path, monkeypatch):
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch, [_FakeResponse(500, {"detail": "boom"})],
        snapshot={"a.md": "old", "b.md": "b-hash"},
    )

    await sync.sync_paths(changed=[_write(kb / "a.md", "# A\n\nnew\n")])

    assert json.loads(snap_path.read_text(encoding="utf-8")) == {
        "a.md": "old", "b.md": "b-hash",
    }


async def test_local_sync_network_error_keeps_snapshot(tmp_path, monkeypatch):
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch, [RuntimeError("conn reset")],
        snapshot={"a.md": "old"},
    )

    await sync.sync_paths(changed=[_write(kb / "a.md", "# A\n\nnew\n")])

    assert json.loads(snap_path.read_text(encoding="utf-8")) == {"a.md": "old"}


async def test_local_sync_rejected_not_in_snapshot(tmp_path, monkeypatch):
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch,
        [_ok(rejected=[{"path": "a.md", "reason": "hash mismatch"}])],
        snapshot={"b.md": "b-hash"},
    )

    await sync.sync_paths(changed=[_write(kb / "a.md", "# A\n\nnew\n")])

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert "a.md" not in snap and snap["b.md"] == "b-hash"


async def test_local_sync_multi_root_prefix(tmp_path, monkeypatch):
    """多知识根：相对路径带目录名前缀，与全量扫描一致。"""
    kb1, kb2 = tmp_path / "kb1", tmp_path / "kb2"
    kb1.mkdir()
    kb2.mkdir()
    sync, calls, _, _ = _make(
        tmp_path, monkeypatch, [_ok(created=1)],
        roots=f"{kb1},{kb2}",
    )

    await sync.sync_paths(changed=[_write(kb2 / "a.md")])

    assert [d["path"] for d in calls["payloads"][0]["documents"]] == ["kb2/a.md"]


async def test_local_sync_updates_documents_cache(tmp_path, monkeypatch):
    """局部同步后 self.documents 与磁盘一致（供 doc_request 回传）。"""
    sync, calls, _, kb = _make(tmp_path, monkeypatch, [_ok(created=1)])
    a = _write(kb / "a.md", "# A\n\nbody\n")

    await sync.sync_paths(changed=[a])

    assert [d.path for d in sync.documents] == ["a.md"]


# ---- 并发保护 ----

async def test_concurrent_sync_serialized(tmp_path, monkeypatch):
    """并发触发被串行化：同一时刻只有一个上传在跑。"""
    import app.sync as sync_mod

    kb = tmp_path / "kb"
    kb.mkdir()
    settings = NodeSettings(hub_api_url="http://test/api", knowledge_roots=str(kb))
    sync = DocumentSync(_FakeTransport(), settings, snapshot_path=tmp_path / "s.json")

    state = {"active": 0, "max_active": 0}

    async def slow_upload(self, payload):
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return _ok()

    monkeypatch.setattr(sync_mod.DocumentSync, "_upload", slow_upload)
    a = _write(kb / "a.md")

    await asyncio.gather(
        sync.sync_paths(changed=[a]),
        sync.sync_paths(changed=[a]),
        sync.sync_paths(changed=[a]),
    )

    assert state["max_active"] == 1


# ---- 局部同步的分批（node-upload-batching） ----

async def test_local_sync_batches_when_over_limit(tmp_path, monkeypatch):
    """批量变更聚合后超过条数上限 → 切分为多批,快照仍按局部语义更新."""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch,
        [
            _ok(created=2),
            _ok(created=1),
        ],
    )
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    for i in range(3):
        _write(kb / f"f{i}.md", f"# T{i}\n\nbody{i}\n")
    changed = [kb / f"f{i}.md" for i in range(3)]

    await sync.sync_paths(changed=changed)

    assert len(calls["payloads"]) == 2
    assert [len(p["documents"]) for p in calls["payloads"]] == [2, 1]
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert all(f"f{i}.md" in snap for i in range(3))


async def test_local_sync_batch_failure_keeps_snapshot(tmp_path, monkeypatch):
    """局部同步分批中途失败 → 快照不动（未被删除的旧条目也保留）."""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch,
        [
            _ok(created=2),
            _FakeResponse(413, "too large"),
        ],
        snapshot={"keep.md": "hash-keep"},
    )
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    for i in range(4):
        _write(kb / f"f{i}.md", f"# T{i}\n\nbody{i}\n")
    changed = [kb / f"f{i}.md" for i in range(4)]

    await sync.sync_paths(changed=changed)

    assert len(calls["payloads"]) == 2  # 中止,不发后续批
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert snap == {"keep.md": "hash-keep"}


# ---- 局部同步的分批（node-upload-batching） ----

async def test_local_sync_batches_when_over_limit(tmp_path, monkeypatch):
    """批量变更聚合后超过条数上限 → 切分为多批,快照仍按局部语义更新."""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch,
        [
            _ok(created=2),
            _ok(created=1),
        ],
    )
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    for i in range(3):
        _write(kb / f"f{i}.md", f"# T{i}\n\nbody{i}\n")
    changed = [kb / f"f{i}.md" for i in range(3)]

    await sync.sync_paths(changed=changed)

    assert len(calls["payloads"]) == 2
    assert [len(p["documents"]) for p in calls["payloads"]] == [2, 1]
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert all(f"f{i}.md" in snap for i in range(3))


async def test_local_sync_batch_failure_keeps_snapshot(tmp_path, monkeypatch):
    """局部同步分批中途失败 → 快照不动（未被删除的旧条目也保留）."""
    sync, calls, snap_path, kb = _make(
        tmp_path, monkeypatch,
        [
            _ok(created=2),
            _FakeResponse(413, "too large"),
        ],
        snapshot={"keep.md": "hash-keep"},
    )
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    for i in range(4):
        _write(kb / f"f{i}.md", f"# T{i}\n\nbody{i}\n")
    changed = [kb / f"f{i}.md" for i in range(4)]

    await sync.sync_paths(changed=changed)

    assert len(calls["payloads"]) == 2  # 中止,不发后续批
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert snap == {"keep.md": "hash-keep"}
