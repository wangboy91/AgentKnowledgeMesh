"""hash-first 同步逻辑单测(app/sync.py).

覆盖 classify_diff 三分类与空目录、build_payload 结构(含 deletions
新协议标记)、sync_documents 成功/失败/rejected 的快照语义。
"""

from app.sync import SyncDiff, build_payload, classify_diff


def _doc(path, content, source="kb"):
    from akm_shared.scanner import ScannedDocument, compute_hash

    return ScannedDocument(
        path=path,
        title=path.replace(".md", ""),
        hash=compute_hash(content),
        size=len(content.encode()),
        content=content,
        source=source,
    )


def test_classify_added_changed_unchanged():
    """新增/变更 → full,未变 → hash_only."""
    from akm_shared.scanner import compute_hash

    snapshot = {"a.md": "stale", "b.md": compute_hash("B")}
    docs = [_doc("a.md", "A2"), _doc("b.md", "B"), _doc("c.md", "C")]

    diff = classify_diff(docs, snapshot)

    assert [d.path for d in diff.full_docs] == ["a.md", "c.md"]
    assert [d.path for d in diff.hash_only] == ["b.md"]
    assert diff.deletions == []


def test_classify_removed_to_deletions():
    """快照有而本轮扫描缺失 → deletions."""
    snapshot = {"a.md": "ha", "gone.md": "hg"}
    docs = [_doc("a.md", "A")]

    diff = classify_diff(docs, snapshot)

    assert diff.deletions == ["gone.md"]


def test_classify_empty_dir_and_empty_snapshot():
    """空目录 + 空快照 → 三类皆空."""
    diff = classify_diff([], {})
    assert diff.full_docs == [] and diff.hash_only == [] and diff.deletions == []


def test_classify_first_run_full_upload():
    """空快照(首次运行/快照丢失)→ 全部按新增携带全文."""
    docs = [_doc("a.md", "A"), _doc("b.md", "B")]
    diff = classify_diff(docs, {})
    assert [d.path for d in diff.full_docs] == ["a.md", "b.md"]
    assert diff.hash_only == [] and diff.deletions == []


def test_build_payload_structure():
    """full 条目含 content,hash-only 条目无 content 键,deletions 键恒在."""
    diff = SyncDiff(
        full_docs=[_doc("a.md", "AAA")],
        hash_only=[_doc("b.md", "B")],
        deletions=["gone.md"],
    )

    payload = build_payload(diff)

    assert payload["deletions"] == ["gone.md"]
    by_path = {d["path"]: d for d in payload["documents"]}
    assert by_path["a.md"]["content"] == "AAA"
    assert "content" not in by_path["b.md"]


# ---- sync_documents 编排(快照语义) ----

from app.config import NodeSettings  # noqa: E402
from app.sync import DocumentSync  # noqa: E402


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


def _make_sync(snapshot_path):
    settings = NodeSettings(hub_api_url="http://test/api", knowledge_roots="")
    sync = DocumentSync(_FakeTransport(), settings, snapshot_path=snapshot_path)
    return sync


def _patch(monkeypatch, docs, responses):
    """固定扫描结果并让 _upload 依次返回预设响应(或抛异常),记录 payload."""
    import app.sync as sync_mod

    calls = {"payloads": []}
    monkeypatch.setattr(sync_mod, "scan_knowledge_roots", lambda roots, max_size_bytes: list(docs))
    it = iter(responses)

    async def fake_upload(self, payload):
        calls["payloads"].append(payload)
        result = next(it)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(sync_mod.DocumentSync, "_upload", fake_upload)
    return calls


async def test_sync_success_updates_snapshot(tmp_path, monkeypatch):
    """成功(200)后快照等于本轮扫描."""
    docs = [_doc("a.md", "A"), _doc("b.md", "B")]
    calls = _patch(
        monkeypatch, docs,
        [_FakeResponse(200, {"created": 2, "updated": 0, "deleted": 0, "rejected": []})],
    )
    sync = _make_sync(tmp_path / "sync_state.json")

    await sync.sync_documents()

    snap = (tmp_path / "sync_state.json").read_text(encoding="utf-8")
    assert '"a.md"' in snap and '"b.md"' in snap
    # 首轮:全部携带全文
    assert all("content" in d for d in calls["payloads"][0]["documents"])
    assert calls["payloads"][0]["deletions"] == []


async def test_sync_failure_keeps_snapshot(tmp_path, monkeypatch):
    """失败响应(500)后快照不变,网络异常同理."""
    snap_path = tmp_path / "sync_state.json"
    snap_path.write_text('{"a.md": "old"}', encoding="utf-8")
    calls = _patch(
        monkeypatch,
        [_doc("a.md", "A2"), _doc("b.md", "B")],
        [_FakeResponse(500, {"detail": "boom"})],
    )
    sync = _make_sync(snap_path)

    await sync.sync_documents()

    assert snap_path.read_text(encoding="utf-8") == '{"a.md": "old"}'
    assert calls["payloads"][0]["deletions"] == []


async def test_sync_network_error_keeps_snapshot(tmp_path, monkeypatch):
    """上传抛网络异常后快照不变."""
    snap_path = tmp_path / "sync_state.json"
    snap_path.write_text('{"a.md": "old"}', encoding="utf-8")
    calls = _patch(monkeypatch, [_doc("a.md", "A2")], [RuntimeError("conn reset")])
    sync = _make_sync(snap_path)

    await sync.sync_documents()

    assert snap_path.read_text(encoding="utf-8") == '{"a.md": "old"}'


async def test_sync_rejected_excluded_from_snapshot(tmp_path, monkeypatch):
    """rejected 条目不入快照(下轮带全文重传)."""
    docs = [_doc("a.md", "A"), _doc("b.md", "B")]
    calls = _patch(
        monkeypatch, docs,
        [_FakeResponse(200, {
            "created": 1, "updated": 0, "deleted": 0,
            "rejected": [{"path": "b.md", "reason": "hash mismatch"}],
        })],
    )
    sync = _make_sync(tmp_path / "sync_state.json")

    await sync.sync_documents()

    snap = (tmp_path / "sync_state.json").read_text(encoding="utf-8")
    assert '"a.md"' in snap and '"b.md"' not in snap
    # b 未在快照 → 本轮以全文上传
    by_path = {d["path"]: d for d in calls["payloads"][0]["documents"]}
    assert "content" in by_path["b.md"]
