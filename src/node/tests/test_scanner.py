"""Markdown 可纳入判定单测（akm_shared.scanner）.

判定是扫描器与文件监听共用的**唯一来源**（add-node-file-watch）：两处语义一旦
漂移，会出现"监听到了但扫描不到"（下次全量对账时该文档被判为删除）或反之的
诡异行为。故逐条覆盖。
"""

from pathlib import Path

from akm_shared.scanner import (
    EXCLUDED_DIR_NAMES,
    is_watchable_markdown,
    scan_knowledge_roots,
    scan_one,
    scan_single_root,
)


def _write(path: Path, text: str = "# T\n\nbody\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- is_watchable_markdown：路径级判定 ----

def test_accepts_markdown_under_root(tmp_path):
    assert is_watchable_markdown(_write(tmp_path / "notes" / "a.md"), tmp_path) is True


def test_rejects_non_markdown(tmp_path):
    assert is_watchable_markdown(_write(tmp_path / "a.txt"), tmp_path) is False
    assert is_watchable_markdown(_write(tmp_path / "a.md.bak"), tmp_path) is False


def test_uppercase_extension_rejected(tmp_path):
    """扩展名区分大小写：与 Linux 下 rglob("*.md") 的行为对齐，两平台一致。"""
    assert is_watchable_markdown(_write(tmp_path / "A.MD"), tmp_path) is False


def test_rejects_hidden_entries(tmp_path):
    assert is_watchable_markdown(_write(tmp_path / ".a.md"), tmp_path) is False
    assert is_watchable_markdown(
        _write(tmp_path / ".hidden" / "a.md"), tmp_path
    ) is False


def test_hidden_root_itself_does_not_reject_children(tmp_path):
    """根目录本身是隐藏目录时，其下文档仍应被接受（回归：基于绝对路径判断会误拒）。"""
    root = tmp_path / ".workbuddy-ai"
    assert is_watchable_markdown(_write(root / "a.md"), root) is True


def test_rejects_builtin_excluded_dirs(tmp_path):
    for name in EXCLUDED_DIR_NAMES:
        assert is_watchable_markdown(_write(tmp_path / name / "a.md"), tmp_path) is False, name


def test_extra_excluded_dirs(tmp_path):
    f = _write(tmp_path / "vendor" / "a.md")
    assert is_watchable_markdown(f, tmp_path) is True
    assert is_watchable_markdown(f, tmp_path, extra_excluded={"vendor"}) is False


def test_rejects_path_outside_root(tmp_path):
    f = _write(tmp_path / "other" / "a.md")
    assert is_watchable_markdown(f, tmp_path / "kb") is False


def test_deleted_file_still_passes_path_check(tmp_path):
    """删除事件必须能通过判定（不能 stat，否则删除无法同步）。"""
    gone = tmp_path / "gone.md"
    assert not gone.exists()
    assert is_watchable_markdown(gone, tmp_path) is True


# ---- scan_one：单文件扫描（监听侧入口） ----

def test_scan_one_size_limit(tmp_path):
    big = _write(tmp_path / "big.md", "x" * 100)
    assert scan_one(big, tmp_path, max_size_bytes=50) is None
    assert scan_one(big, tmp_path, max_size_bytes=200) is not None


def test_scan_one_missing_file(tmp_path):
    assert scan_one(tmp_path / "nope.md", tmp_path) is None


def test_scan_one_matches_scan_single_root(tmp_path):
    """单文件扫描与目录扫描对同一文件产出一致（路径 / 标题 / hash / size）。"""
    _write(tmp_path / "sub" / "a.md", "# 标题\n\n内容\n")
    _write(tmp_path / "b.md", "plain\n")

    one = scan_one(tmp_path / "sub" / "a.md", tmp_path)
    by_path = {d.path: d for d in scan_single_root(tmp_path)}

    assert one is not None
    assert one.path == "sub/a.md"
    assert one.title == "标题"
    assert by_path["sub/a.md"].hash == one.hash
    assert by_path["sub/a.md"].size == one.size


def test_scan_one_prefix_matches_multi_root(tmp_path):
    """多知识根场景：前缀规则与 scan_knowledge_roots 一致。"""
    r1, r2 = tmp_path / "kb1", tmp_path / "kb2"
    _write(r1 / "a.md")
    _write(r2 / "a.md")

    assert {d.path for d in scan_knowledge_roots([r1, r2])} == {"kb1/a.md", "kb2/a.md"}

    one = scan_one(r1 / "a.md", r1, prefix=r1.name)
    assert one is not None and one.path == "kb1/a.md"


# ---- scan_single_root：目录扫描仍跳过排除项 ----

def test_scan_single_root_skips_excluded(tmp_path):
    _write(tmp_path / "keep.md")
    _write(tmp_path / "node_modules" / "skip.md")
    _write(tmp_path / ".git" / "skip.md")

    assert [d.path for d in scan_single_root(tmp_path)] == ["keep.md"]
