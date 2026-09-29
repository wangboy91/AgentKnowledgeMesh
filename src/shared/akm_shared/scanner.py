"""Markdown 文件扫描器（Hub 与 Node 共用）.

职责：
1. 递归扫描知识库目录下的 .md 文件
2. 提取文档元信息（标题、路径、大小、hash）
3. 读取文件内容

设计要点：
- 标题提取：优先读取首行 # Title，无则用文件名（去掉 .md）
- Hash 计算：SHA256，用于增量更新检测
- 支持多个知识库目录（多目录时以目录名为路径前缀）
- 返回扁平列表，由调用方（indexer / sync）负责后续处理
- **可纳入判定的唯一来源**：`is_watchable_markdown` 与 `within_size_limit`。
  扫描与文件监听（add-node-file-watch）共用这两个判定——两处语义若漂移，
  会出现"监听到了但扫描不到"（文档被误判删除）或反之的诡异行为。
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# 默认单文件大小上限（10MB），调用方可通过 max_size_bytes 覆盖
DEFAULT_MAX_SIZE_BYTES = 10 * 1024 * 1024

# 内置排除目录名：只列不以 "." 开头的（点开头的目录由隐藏项规则覆盖）。
# 扫描器与文件监听共用，避免把依赖/构建产物中的 Markdown 纳入知识库。
EXCLUDED_DIR_NAMES = frozenset({
    "__pycache__",
    "node_modules",
    "dist",
    "build",
})


@dataclass
class ScannedDocument:
    """扫描结果数据类."""

    path: str          # 相对路径，如 "projects/ai-crm.md"
    title: str         # 文档标题
    hash: str          # 文件 SHA256
    size: int          # 文件大小（字节）
    content: str       # 文件全文
    source: str        # 来源目录名


def extract_title(content: str, filename: str) -> str:
    """从 Markdown 内容提取标题.

    优先级：
    1. 首行 # 标题
    2. 文件名（去掉 .md 扩展名）
    """
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return filename.replace(".md", "").replace("_", " ").replace("-", " ")


def compute_hash(content: str) -> str:
    """计算内容 SHA256."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_watchable_markdown(
    path: Path,
    root: Path,
    *,
    extra_excluded: Iterable[str] = (),
) -> bool:
    """路径级判定：该路径是否属于 root 下应纳入知识库的 Markdown。

    供扫描器与文件监听共用（见模块 docstring）。**只做路径判定，不访问文件
    系统**——监听侧会收到已删除文件的 deleted 事件，此处若 stat 会把删除事件
    误过滤掉，导致删除无法同步到 Hub。

    判定项：扩展名、位于 root 之下、相对路径无隐藏项、不在排除目录内。
    单文件大小上限不在此判定，由 `scan_one` 在读取阶段施加。
    """
    if path.suffix != ".md":
        return False
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False

    parts = relative.parts
    if not parts:
        return False
    # 隐藏项：必须基于相对路径判断——基于绝对路径时，根目录本身若是隐藏目录
    # （如 .workbuddy-ai），整个根会被误跳过，导致该知识根不参与扫描
    if any(part.startswith(".") for part in parts):
        return False
    # 只判定目录部分：文件名恰好叫 node_modules 的情形极罕见，且无 .md
    # 扩展名时已被扩展名规则排除
    excluded = EXCLUDED_DIR_NAMES | set(extra_excluded)
    if any(part in excluded for part in parts[:-1]):
        return False
    return True


def scan_one(
    path: Path,
    root: Path,
    *,
    prefix: str = "",
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
    extra_excluded: Iterable[str] = (),
) -> ScannedDocument | None:
    """扫描单个文件并构造结果；不满足判定或读取失败时返回 None。

    与 `scan_single_root` 共用同一套判定（`is_watchable_markdown` + 大小上限
    + 可读性），供文件监听触发的局部增量使用——保证"监听到的"与"扫描到的"
    完全一致。
    """
    if not is_watchable_markdown(path, root, extra_excluded=extra_excluded):
        return None
    try:
        file_size = path.stat().st_size
    except OSError:
        return None
    if file_size > max_size_bytes:
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError):
        return None

    # 相对路径统一使用 POSIX 分隔符(/)，避免 Windows 下产出 \ 混入文档路径，
    # 导致 URL 导航、树构建与跨端查找不一致（见 akm 路径规范）
    relative_path = path.relative_to(root).as_posix()
    if prefix:
        relative_path = f"{prefix}/{relative_path}"

    return ScannedDocument(
        path=relative_path,
        title=extract_title(content, path.stem),
        hash=compute_hash(content),
        size=file_size,
        content=content,
        source=root.name,
    )


def scan_single_root(
    root: Path,
    prefix: str = "",
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
) -> list[ScannedDocument]:
    """扫描单个知识库目录.

    Args:
        root: 知识库根目录
        prefix: 路径前缀（用于多目录时区分来源）
        max_size_bytes: 单文件大小上限（字节）

    Returns:
        扫描到的文档列表
    """
    if not root.exists():
        return []

    documents = []
    for md_file in root.rglob("*.md"):
        # 判定统一走 scan_one → is_watchable_markdown（与文件监听共用）。
        # 注：rglob("*.md") 在 Windows 上大小写不敏感，会返回 .MD；判定按
        # 精确小写后缀过滤，与 Linux 下的 rglob 行为对齐，两平台结果一致。
        doc = scan_one(md_file, root, prefix=prefix, max_size_bytes=max_size_bytes)
        if doc is not None:
            documents.append(doc)

    return documents


def scan_knowledge_roots(
    roots: list[Path],
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
) -> list[ScannedDocument]:
    """扫描所有配置的知识库目录.

    单目录时不加前缀，多目录时用目录名作为前缀，避免不同目录间路径冲突。

    Args:
        roots: 知识库目录列表
        max_size_bytes: 单文件大小上限（字节）

    Returns:
        扫描到的文档列表
    """
    if len(roots) == 1:
        return scan_single_root(roots[0], max_size_bytes=max_size_bytes)

    all_documents = []
    for root in roots:
        docs = scan_single_root(root, prefix=root.name, max_size_bytes=max_size_bytes)
        all_documents.extend(docs)

    return all_documents
