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


# ---- 显式状态目录优先(node-state-isolation) ----

def test_explicit_state_dir_wins_over_repo_snapshot(tmp_path):
    """显式指定状态目录时,包内既有快照不得抢占(多环境隔离的基础)."""
    from app.state import resolve_snapshot_path

    repo = tmp_path / "repo" / "sync_state.json"
    repo.parent.mkdir()
    repo.write_text("{}", encoding="utf-8")
    prod = tmp_path / "prod" / "sync_state.json"

    assert resolve_snapshot_path(repo, prod, explicit=True) == prod


def test_explicit_state_dir_wins_when_repo_snapshot_absent(tmp_path):
    """显式指定时包内无快照亦走显式目录(与隐式分支结果一致但路径来源不同)."""
    from app.state import resolve_snapshot_path

    repo = tmp_path / "repo" / "sync_state.json"  # 不创建
    prod = tmp_path / "prod" / "sync_state.json"

    assert resolve_snapshot_path(repo, prod, explicit=True) == prod


def test_not_explicit_keeps_legacy_behaviour(tmp_path):
    """未显式指定时沿用旧语义:包内存在则包内,否则用户目录;默认参数等价 explicit=False."""
    from app.state import resolve_snapshot_path

    repo = tmp_path / "repo" / "sync_state.json"
    repo.parent.mkdir()
    user = tmp_path / "user" / "sync_state.json"

    repo.write_text("{}", encoding="utf-8")
    assert resolve_snapshot_path(repo, user, explicit=False) == repo
    assert resolve_snapshot_path(repo, user) == repo  # 默认参数

    repo.unlink()
    assert resolve_snapshot_path(repo, user, explicit=False) == user
    assert resolve_snapshot_path(repo, user) == user


def _state_probe(env: dict) -> tuple[bool, Path]:
    """在子进程中读取 (USER_STATE_DIR_EXPLICIT, DEFAULT_SNAPSHOT_PATH).

    必须用子进程:DEFAULT_SNAPSHOT_PATH 在模块 import 时求值,本进程内改不了。
    不触碰仓库工作区——快照位置由"显式标识"决定,无需真造一个仓内快照文件。
    """
    import subprocess
    import sys

    node_dir = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.state import DEFAULT_SNAPSHOT_PATH as p, USER_STATE_DIR_EXPLICIT as e;"
            "print(f'{int(e)}|{p}')",
        ],
        cwd=str(node_dir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    flag, _, path = proc.stdout.strip().partition("|")
    return flag == "1", Path(path)


def test_default_snapshot_path_follows_process_env(tmp_path):
    """接线验证:设了 AKM_NODE_STATE_DIR 时默认快照即为该目录,且标识为显式."""
    import os

    prod_dir = tmp_path / "akm-node-prod"

    explicit, path = _state_probe(dict(os.environ, AKM_NODE_STATE_DIR=str(prod_dir)))
    assert explicit is True
    assert path == prod_dir / "sync_state.json"


def test_default_snapshot_path_not_explicit_without_env():
    """回归:未设该变量时标识为 False,默认分支不受显式分支影响."""
    import os

    explicit, _ = _state_probe(
        {k: v for k, v in os.environ.items() if k != "AKM_NODE_STATE_DIR"}
    )
    assert explicit is False

