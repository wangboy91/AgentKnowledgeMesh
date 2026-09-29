"""监听循环辅助逻辑单测（app/runner.py）.

覆盖 watchfiles 过滤回调（必须与扫描器共用判定）、变更事件拆分（删除必须单独
收集，否则局部同步会漏删）、写入稳定性检查。
"""

from watchfiles import Change

from app.runner import HubClient, _make_watch_filter, _split_changes


# ---- 过滤回调 ----

def test_watch_filter_accepts_markdown(tmp_path):
    flt = _make_watch_filter([tmp_path], set())
    assert flt(Change.added, str(tmp_path / "a.md")) is True


def test_watch_filter_rejects_non_markdown_and_excluded(tmp_path):
    flt = _make_watch_filter([tmp_path], set())
    assert flt(Change.added, str(tmp_path / "a.txt")) is False
    assert flt(Change.added, str(tmp_path / "node_modules" / "a.md")) is False


def test_watch_filter_accepts_deleted_path(tmp_path):
    """删除事件的文件已不存在，过滤回调不能 stat，否则删除被丢弃。"""
    flt = _make_watch_filter([tmp_path], set())
    assert flt(Change.deleted, str(tmp_path / "gone.md")) is True


def test_watch_filter_respects_extra_excluded(tmp_path):
    flt = _make_watch_filter([tmp_path], {"vendor"})
    assert flt(Change.added, str(tmp_path / "vendor" / "a.md")) is False


def test_watch_filter_matches_any_root(tmp_path):
    r1, r2 = tmp_path / "kb1", tmp_path / "kb2"
    r1.mkdir()
    r2.mkdir()
    flt = _make_watch_filter([r1, r2], set())
    assert flt(Change.added, str(r2 / "a.md")) is True
    assert flt(Change.added, str(tmp_path / "other" / "a.md")) is False


# ---- 变更事件拆分 ----

def test_split_changes_separates_deleted(tmp_path):
    a, b, gone = tmp_path / "a.md", tmp_path / "b.md", tmp_path / "gone.md"
    changed, deleted = _split_changes({
        (Change.added, str(a)),
        (Change.modified, str(b)),
        (Change.deleted, str(gone)),
    })

    assert set(changed) == {a, b}
    assert deleted == [gone]


def test_split_changes_dedupes_same_path(tmp_path):
    a = tmp_path / "a.md"
    changed, deleted = _split_changes({
        (Change.added, str(a)),
        (Change.modified, str(a)),
    })

    assert changed == [a]
    assert deleted == []


# ---- 写入稳定性检查 ----

async def test_is_stable_true_for_untouched_file(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# A\n", encoding="utf-8")

    assert await HubClient._is_stable(f) is True


async def test_is_stable_false_for_missing_file(tmp_path):
    assert await HubClient._is_stable(tmp_path / "nope.md") is False


# ---- 循环开关（关闭时必须立即返回，不能忙轮询） ----

class _StubClient:
    """只为循环体提供 transport.settings 的最小替身。"""

    def __init__(self, **overrides):
        from app.config import NodeSettings

        class _T:
            settings = NodeSettings(
                hub_api_url="http://test/api", knowledge_roots="", **overrides
            )

        self.transport = _T()


async def test_watch_loop_returns_when_disabled():
    """AKM_WATCH_ENABLED=false → 监听循环立即返回。"""
    import asyncio

    client = _StubClient(watch_enabled=False)

    await asyncio.wait_for(HubClient._watch_loop(client), timeout=1.0)


async def test_reconcile_loop_returns_when_interval_zero():
    """对账间隔 0 → 循环立即返回，不进入忙轮询。"""
    import asyncio

    client = _StubClient(watch_reconcile_seconds=0)

    await asyncio.wait_for(HubClient._reconcile_loop(client), timeout=1.0)
