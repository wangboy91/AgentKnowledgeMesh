"""Markdown 扫描器薄包装.

扫描逻辑已下沉到共享包 akm_shared.scanner，本模块仅负责：
1. 向 app 内部再导出共享类型与工具函数
2. 注入 Hub 配置（知识库目录 + 单文件大小上限），保留原有 async 签名

调用方（api/documents.py、indexer.py）无需改动。
"""

from app.config import settings
from akm_shared.scanner import (
    ScannedDocument,
    compute_hash,
    extract_title,
    scan_knowledge_roots as _scan_knowledge_roots,
)

__all__ = ["ScannedDocument", "extract_title", "compute_hash", "scan_knowledge_root"]


async def scan_knowledge_root() -> list[ScannedDocument]:
    """扫描所有配置的知识库目录.

    Returns:
        扫描到的文档列表
    """
    return _scan_knowledge_roots(
        settings.knowledge_paths,
        max_size_bytes=settings.max_file_size_mb * 1024 * 1024,
    )
