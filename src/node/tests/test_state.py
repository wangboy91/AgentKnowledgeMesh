"""同步快照读写单测(app/state.py)."""

from pathlib import Path

from app.state import load_snapshot, save_snapshot


def test_roundtrip(tmp_path):
    """写入后读回应得到相同快照."""
    path = tmp_path / "sync_state.json"
    save_snapshot({"a.md": "h1", "sub/b.md": "h2"}, path)
    assert load_snapshot(path) == {"a.md": "h1", "sub/b.md": "h2"}


def test_missing_file_returns_empty(tmp_path):
    """文件缺失(首次运行)按空快照处理."""
    assert load_snapshot(tmp_path / "sync_state.json") == {}


def test_corrupt_file_self_heals(tmp_path):
    """损坏文件(半写 JSON)按空快照自愈."""
    path = tmp_path / "sync_state.json"
    path.write_text('{"a.md": "h1"', encoding="utf-8")
    assert load_snapshot(path) == {}


def test_non_dict_self_heals(tmp_path):
    """合法 JSON 但非字典(如列表)按空快照自愈."""
    path = tmp_path / "sync_state.json"
    path.write_text('["not", "a", "dict"]', encoding="utf-8")
    assert load_snapshot(path) == {}


def test_atomic_write_no_tmp_left(tmp_path):
    """写入后不留 .tmp 残留文件."""
    path = tmp_path / "sync_state.json"
    save_snapshot({"a.md": "h1"}, path)
    assert list(tmp_path.iterdir()) == [path]


def test_creates_parent_dirs(tmp_path):
    """父目录不存在时自动创建."""
    save_snapshot({"a.md": "h1"}, tmp_path / "nested/dir/sync_state.json")
    assert (tmp_path / "nested/dir/sync_state.json").exists()


# ---- 快照位置选择(安装版 vs 开发仓) ----

def test_resolve_snapshot_path_prefers_existing_repo_snapshot(tmp_path):
    """开发仓位置已有快照时继续用原位置(存量开发状态无感迁移)."""
    from app.state import resolve_snapshot_path

    repo = tmp_path / "repo" / "sync_state.json"
    repo.parent.mkdir()
    repo.write_text("{}", encoding="utf-8")
    user = tmp_path / "user" / "sync_state.json"

    assert resolve_snapshot_path(repo, user) == repo


def test_resolve_snapshot_path_falls_back_to_user_dir(tmp_path):
    """开发仓位置无快照(安装版/首次运行)时用用户目录."""
    from app.state import resolve_snapshot_path

    repo = tmp_path / "repo" / "sync_state.json"  # 不创建
    user = tmp_path / "user" / "sync_state.json"

    assert resolve_snapshot_path(repo, user) == user
