"""文档写入口径单源(create / update).

所有"新建或覆盖文档正文"的入口(REST `POST /api/documents`、
`PUT /api/documents/{doc_id}`,Hub MCP 的 create_document / update_document)
均经由本模块,统一:

- 标题提取(内容前 5 行 `# ` → 路径文件名)
- SHA256 与字节大小重算
- ``rag_status`` 策略(``initial_rag_status`` / ``resolve_rag_status``)
- 提交与 refresh

避免 REST 与 MCP 两处各写一份导致 hash / 标题 / rag_status 漂移。

本模块 **不做** 权限与作用域校验(那是端点职责),也 **不派发** 向量维护:
调用方以 ``doc.rag_status == "indexed"`` 作为"应派发后台索引"的信号——
该等式与 ``should_auto_index(rag_mode, vectorization_enabled)`` 等价
(见 ``services/rag/sync.py``),无需重复读设置。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.rag.sync import (
    get_rag_mode,
    get_vectorization_enabled,
    initial_rag_status,
    resolve_rag_status,
)


class PathConflict(Exception):
    """同一 (node_id, path) 下文档已存在."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Document already exists at this path: {path}")


def upsert_payload(doc: Document, pending: bool = False) -> dict:
    """构造后台向量索引载荷(写入口径与 RAG 勾选流程共用).

    ``pending=True`` 供"勾选加入 RAG"流程使用(嵌入完成后回写 indexed);
    写回通道不带该键——初始状态已在入库时按策略设定。
    """
    return {
        "doc_id": doc.id,
        "title": doc.title,
        "path": doc.path,
        "content": doc.content,
        "node_id": doc.node_id,
        "pending": pending,
    }


def _content_hash(content: str) -> str:
    """正文的 SHA256(与节点扫描 / 上传口径一致)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _content_size(content: str) -> int:
    """正文字节大小(UTF-8)."""
    return len(content.encode("utf-8"))


def _title_from_content(content: str) -> str | None:
    """从内容前 5 行提取 `# ` 一级标题;无则 None."""
    for line in content.split("\n")[:5]:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


async def create_document(
    session: AsyncSession,
    *,
    node_id: str,
    path: str,
    content: str,
    title: str | None = None,
) -> Document:
    """新建文档并入库.

    唯一性以 ``(node_id, path)`` 判定,冲突抛 :class:`PathConflict`。
    标题缺省或为空时,先取内容首个 `# ` 标题,再退化为路径文件名(去扩展名)。
    调用方负责:作用域归属(node_id)的确定与权限校验、commit 后的向量派发。
    """
    existing = await session.execute(
        select(Document).where(Document.node_id == node_id, Document.path == path)
    )
    if existing.scalar_one_or_none():
        raise PathConflict(path)

    resolved_title = title or _title_from_content(content) or Path(path).stem

    rag_mode = await get_rag_mode(session)
    vectorization_enabled = await get_vectorization_enabled(session)

    doc = Document(
        node_id=node_id,
        path=path,
        title=resolved_title,
        hash=_content_hash(content),
        size=_content_size(content),
        content=content,
        rag_status=initial_rag_status(rag_mode, vectorization_enabled),
    )
    session.add(doc)
    await session.commit()
    # 服务端生成列(created_at/updated_at)写入后可能被过期,显式 refresh 才能安全序列化
    await session.refresh(doc)
    return doc


async def update_document(session: AsyncSession, doc: Document, content: str) -> Document:
    """覆盖更新文档正文并重算元信息.

    标题仅在内容前 5 行存在 `# ` 时更新(否则保留原值,与既有行为一致)。
    ``excluded`` 状态由 :func:`resolve_rag_status` 保持(用户显式移出不因内容变更被拉回)。
    调用方负责:作用域校验与 commit 后的向量派发。
    """
    doc.content = content
    doc.hash = _content_hash(content)
    doc.size = _content_size(content)

    extracted = _title_from_content(content)
    if extracted:
        doc.title = extracted

    rag_mode = await get_rag_mode(session)
    vectorization_enabled = await get_vectorization_enabled(session)
    doc.rag_status = resolve_rag_status(doc.rag_status, rag_mode, vectorization_enabled)

    await session.commit()
    await session.refresh(doc)
    return doc
