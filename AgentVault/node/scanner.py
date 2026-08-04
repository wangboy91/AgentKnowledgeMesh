"""Node 端 Markdown 扫描器.

复用 Hub 端的扫描逻辑，用于本地文档索引。
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScannedDocument:
    """扫描结果."""

    path: str
    title: str
    hash: str
    size: int
    content: str


def extract_title(content: str, filename: str) -> str:
    """从 Markdown 内容提取标题."""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return filename.replace(".md", "").replace("_", " ").replace("-", " ")


def compute_hash(content: str) -> str:
    """计算内容 SHA256."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def scan_single_root(root: Path) -> list[ScannedDocument]:
    """扫描单个目录."""
    if not root.exists():
        return []

    documents = []
    max_size = 10 * 1024 * 1024  # 10MB

    for md_file in root.rglob("*.md"):
        # 跳过隐藏文件
        if any(part.startswith(".") for part in md_file.parts):
            continue

        file_size = md_file.stat().st_size
        if file_size > max_size:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            relative_path = str(md_file.relative_to(root))

            documents.append(ScannedDocument(
                path=relative_path,
                title=extract_title(content, md_file.stem),
                hash=compute_hash(content),
                size=file_size,
                content=content,
            ))
        except (UnicodeDecodeError, PermissionError):
            continue

    return documents


def scan_knowledge_roots(roots: list[Path]) -> list[ScannedDocument]:
    """扫描所有知识库目录."""
    all_documents = []

    if len(roots) == 1:
        all_documents = scan_single_root(roots[0])
    else:
        for root in roots:
            docs = scan_single_root(root)
            # 多目录时添加目录名前缀
            for doc in docs:
                doc.path = f"{root.name}/{doc.path}"
            all_documents.extend(docs)

    return all_documents
