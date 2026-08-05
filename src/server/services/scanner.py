"""Markdown 文件扫描器.

职责：
1. 递归扫描知识库目录下的 .md 文件
2. 提取文档元信息（标题、路径、大小、hash）
3. 读取文件内容

设计要点：
- 标题提取：优先读取首行 # Title，无则用文件名（去掉 .md）
- Hash 计算：SHA256，用于增量更新检测
- 支持多个知识库目录
- 返回扁平列表，由 indexer 负责同步到数据库
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from config import settings


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


def scan_single_root(root: Path, prefix: str = "") -> list[ScannedDocument]:
    """扫描单个知识库目录.

    Args:
        root: 知识库根目录
        prefix: 路径前缀（用于多目录时区分来源）

    Returns:
        扫描到的文档列表
    """
    if not root.exists():
        return []

    documents = []
    max_size = settings.max_file_size_mb * 1024 * 1024
    source_name = root.name

    for md_file in root.rglob("*.md"):
        # 跳过隐藏文件和目录
        if any(part.startswith(".") for part in md_file.parts):
            continue

        # 跳过过大的文件
        file_size = md_file.stat().st_size
        if file_size > max_size:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            relative_path = str(md_file.relative_to(root))

            # 如果有前缀，加上前缀
            if prefix:
                relative_path = f"{prefix}/{relative_path}"

            documents.append(ScannedDocument(
                path=relative_path,
                title=extract_title(content, md_file.stem),
                hash=compute_hash(content),
                size=file_size,
                content=content,
                source=source_name,
            ))
        except (UnicodeDecodeError, PermissionError):
            # 跳过无法读取的文件
            continue

    return documents


async def scan_knowledge_root() -> list[ScannedDocument]:
    """扫描所有配置的知识库目录.

    Returns:
        扫描到的文档列表
    """
    all_documents = []
    roots = settings.knowledge_paths

    # 单目录时不加前缀，多目录时用目录名作为前缀
    if len(roots) == 1:
        all_documents = scan_single_root(roots[0])
    else:
        for root in roots:
            docs = scan_single_root(root, prefix=root.name)
            all_documents.extend(docs)

    return all_documents
