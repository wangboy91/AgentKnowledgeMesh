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


async def test_sync_defaults_snapshot_path_when_omitted(tmp_path, monkeypatch):
    """未显式传 snapshot_path 时落到默认路径,不崩溃.

    回归:runner 构造 DocumentSync 时不传 snapshot_path,__init__ 留下的
    None 直接进了 load_snapshot,触发 'NoneType' object has no attribute
    'read_text'(见 app/state.py 的 except 只兜 OSError/ValueError)。
    """
    import app.state as state

    default_path = tmp_path / "data" / "sync_state.json"
    monkeypatch.setattr(state, "DEFAULT_SNAPSHOT_PATH", default_path)

    settings = NodeSettings(hub_api_url="http://test/api", knowledge_roots="")
    sync = DocumentSync(_FakeTransport(), settings)
    calls = _patch(
        monkeypatch,
        [_doc("a.md", "A")],
        [_FakeResponse(200, {"created": 1, "updated": 0, "deleted": 0, "rejected": []})],
    )

    await sync.sync_documents()

    assert default_path.exists()
    assert '"a.md"' in default_path.read_text(encoding="utf-8")


# ---- 分批切分(node-upload-batching) ----

from app.sync import batch_payload, merge_stats, _doc_entry  # noqa: E402


def test_batch_no_limit_returns_single_batch():
    """未触发任何上限 → 单批,结构与本变更引入前一致."""
    diff = SyncDiff(
        full_docs=[_doc("a.md", "AAA")],
        hash_only=[_doc("b.md", "B")],
        deletions=["gone.md"],
    )

    batches = batch_payload(diff, batch_bytes=512 * 1024, batch_docs=50)

    assert len(batches) == 1
    assert batches[0]["deletions"] == ["gone.md"]
    by_path = {d["path"]: d for d in batches[0]["documents"]}
    assert by_path["a.md"]["content"] == "AAA"
    assert "content" not in by_path["b.md"]


def test_batch_single_batch_matches_build_payload():
    """单批结果与 build_payload 逐字段一致(未超限时行为不变的回归保证)."""
    diff = SyncDiff(
        full_docs=[_doc("a.md", "AAA")],
        hash_only=[_doc("c.md", "C")],
        deletions=["old.md"],
    )

    assert batch_payload(diff, 10**9, 10**9) == [build_payload(diff)]


def test_batch_splits_by_doc_count():
    """条数触顶切分:5 篇、每批 2 篇 → 3 批,不重不漏."""
    diff = SyncDiff(full_docs=[_doc(f"{i}.md", f"C{i}") for i in range(5)])

    batches = batch_payload(diff, batch_bytes=0, batch_docs=2)

    assert [len(b["documents"]) for b in batches] == [2, 2, 1]
    paths = [d["path"] for b in batches for d in b["documents"]]
    assert sorted(paths) == sorted(f"{i}.md" for i in range(5))


def test_batch_splits_by_bytes():
    """体积触顶切分:每篇约 1KB,上限 2500 字节 → 每批 2 篇左右."""
    diff = SyncDiff(full_docs=[_doc(f"{i}.md", "x" * 1024) for i in range(5)])

    batches = batch_payload(diff, batch_bytes=2500, batch_docs=0)

    assert len(batches) > 1
    for b in batches:
        assert len(b["documents"]) <= 2
    paths = [d["path"] for b in batches for d in b["documents"]]
    assert sorted(paths) == sorted(f"{i}.md" for i in range(5))


def test_batch_oversized_doc_gets_own_batch():
    """单篇超限独占一批,不被跳过,也不阻塞其余文档."""
    huge = _doc("huge.md", "x" * 5000)
    diff = SyncDiff(full_docs=[_doc("a.md", "A"), huge, _doc("b.md", "B")])

    batches = batch_payload(diff, batch_bytes=2048, batch_docs=0)

    paths = [d["path"] for b in batches for d in b["documents"]]
    assert "huge.md" in paths  # 未被跳过
    assert sorted(paths) == ["a.md", "b.md", "huge.md"]
    owns = [b for b in batches if any(d["path"] == "huge.md" for d in b["documents"])]
    assert len(owns) == 1 and len(owns[0]["documents"]) == 1


def test_batch_deletions_only_in_last_batch():
    """deletions 仅随最后一批;前序批次带空列表(关闭隐式删除推导)."""
    diff = SyncDiff(
        full_docs=[_doc(f"{i}.md", f"C{i}") for i in range(5)],
        deletions=["gone1.md", "gone2.md"],
    )

    batches = batch_payload(diff, batch_bytes=0, batch_docs=2)

    assert len(batches) == 3
    for b in batches[:-1]:
        assert b["deletions"] == []
    assert batches[-1]["deletions"] == ["gone1.md", "gone2.md"]
    # 每批都必须带 deletions 键
    assert all("deletions" in b for b in batches)


def test_batch_empty_diff_emits_one_batch_with_deletions():
    """空 diff → 仍发一批(携带 deletions),保持既有行为."""
    diff = SyncDiff(deletions=["gone.md"])

    batches = batch_payload(diff, 512 * 1024, 50)

    assert batches == [{"documents": [], "deletions": ["gone.md"]}]


def test_doc_entry_size_estimates_utf8_not_chars():
    """体积估算按 UTF-8 字节(中文 3 字节),不是字符数."""
    h_ascii, size_ascii = _doc_entry(_doc("a.md", "abc"), with_content=True)
    h_cjk, size_cjk = _doc_entry(_doc("a.md", "中文内容"), with_content=True)

    assert h_ascii["content"] == "abc"
    assert size_cjk - size_ascii == len("中文内容".encode("utf-8")) - 3


def test_doc_entry_hash_only_no_content_key():
    """hash-only 条目不含 content 键,体积不计正文."""
    entry, size = _doc_entry(_doc("a.md", "x" * 1000), with_content=False)

    assert "content" not in entry
    assert size < 1000


def test_merge_stats_sums_and_concatenates_rejected():
    """跨批统计:数值求和,rejected 列表拼接."""
    merged = merge_stats([
        {"created": 2, "updated": 1, "deleted": 0, "rejected": [{"path": "x"}]},
        {"created": 1, "updated": 0, "deleted": 3, "rejected": [{"path": "y"}]},
    ])

    assert merged == {
        "created": 3, "updated": 1, "deleted": 3,
        "rejected": [{"path": "x"}, {"path": "y"}],
    }


def test_merge_stats_tolerates_missing_rejected():
    """响应缺 rejected 字段时不崩溃(求和按 0 计)."""
    merged = merge_stats([{"created": 1}])
    assert merged["created"] == 1 and merged["rejected"] == []


async def test_multi_batch_success_updates_snapshot(tmp_path, monkeypatch):
    """多批全部成功 → 快照正常落盘,统计为各批之和."""
    docs = [_doc(f"{i}.md", f"C{i}") for i in range(5)]
    calls = _patch(
        monkeypatch, docs,
        [
            _FakeResponse(200, {"created": 2, "updated": 0, "deleted": 0, "rejected": []}),
            _FakeResponse(200, {"created": 2, "updated": 0, "deleted": 0, "rejected": []}),
            _FakeResponse(200, {"created": 1, "updated": 0, "deleted": 0, "rejected": []}),
        ],
    )
    snap_path = tmp_path / "sync_state.json"
    sync = _make_sync(snap_path)
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    await sync.sync_documents()

    assert len(calls["payloads"]) == 3
    snap = snap_path.read_text(encoding="utf-8")
    assert all(f'"{i}.md"' in snap for i in range(5))


async def test_multi_batch_partial_failure_keeps_snapshot(tmp_path, monkeypatch):
    """分批过程中某批失败 → 整体失败,快照不动(下轮重传)."""
    snap_path = tmp_path / "sync_state.json"
    snap_path.write_text('{"old.md": "h"}', encoding="utf-8")
    docs = [_doc(f"{i}.md", f"C{i}") for i in range(5)]
    calls = _patch(
        monkeypatch, docs,
        [
            _FakeResponse(200, {"created": 2, "updated": 0, "deleted": 0, "rejected": []}),
            _FakeResponse(413, "Request Entity Too Large"),
        ],
    )
    sync = _make_sync(snap_path)
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    await sync.sync_documents()

    # 第 1 批成功、第 2 批失败 → 中止,不发第 3 批
    assert len(calls["payloads"]) == 2
    assert snap_path.read_text(encoding="utf-8") == '{"old.md": "h"}'


async def test_multi_batch_network_error_keeps_snapshot(tmp_path, monkeypatch):
    """分批过程中网络异常 → 整体失败,快照不动."""
    snap_path = tmp_path / "sync_state.json"
    snap_path.write_text('{"old.md": "h"}', encoding="utf-8")
    docs = [_doc(f"{i}.md", f"C{i}") for i in range(4)]
    calls = _patch(
        monkeypatch, docs,
        [
            _FakeResponse(200, {"created": 2, "updated": 0, "deleted": 0, "rejected": []}),
            RuntimeError("conn reset"),
        ],
    )
    sync = _make_sync(snap_path)
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    await sync.sync_documents()

    assert len(calls["payloads"]) == 2
    assert snap_path.read_text(encoding="utf-8") == '{"old.md": "h"}'


async def test_multi_batch_rejected_aggregated_across_batches(tmp_path, monkeypatch):
    """跨批 rejected 汇总后统一决策快照."""
    docs = [_doc(f"{i}.md", f"C{i}") for i in range(4)]
    _patch(
        monkeypatch, docs,
        [
            _FakeResponse(200, {
                "created": 1, "updated": 0, "deleted": 0,
                "rejected": [{"path": "0.md", "reason": "hash mismatch"}],
            }),
            _FakeResponse(200, {
                "created": 2, "updated": 0, "deleted": 0,
                "rejected": [{"path": "3.md", "reason": "hash mismatch"}],
            }),
        ],
    )
    snap_path = tmp_path / "sync_state.json"
    sync = _make_sync(snap_path)
    sync.settings.upload_batch_bytes = 0
    sync.settings.upload_batch_docs = 2

    await sync.sync_documents()

    snap = snap_path.read_text(encoding="utf-8")
    assert '"0.md"' not in snap and '"3.md"' not in snap
    assert '"1.md"' in snap and '"2.md"' in snap
