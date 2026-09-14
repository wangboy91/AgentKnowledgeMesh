"""hub 扫描作用域与路径分隔符回归测试.

覆盖:
- hub 本机扫描(scan→sync_documents)只管理 node_id="local",绝不删改节点文档
- 共享扫描器产出的路径统一使用 / 分隔符(Windows 下不再混入 \\)
"""

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.document import Document
from app.services.indexer import sync_documents
from akm_shared.scanner import ScannedDocument, scan_knowledge_roots


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed_document(session_factory, node_id, path, content):
    async with session_factory() as session:
        session.add(Document(
            node_id=node_id, path=path, title=path, hash="h-" + path,
            size=len(content), content=content,
        ))
        await session.commit()


async def test_hub_scan_does_not_touch_node_docs(db):
    """hub 扫描(仅 local 作用域)不应把节点文档判为已删除."""
    await _seed_document(db, "local", "local.md", "l")
    await _seed_document(db, "node-1", "node/secret.md", "n")

    scanned = [ScannedDocument(
        path="local.md", title="Local", hash="h-local.md",
        size=1, content="l", source="sk",
    )]
    async with db() as session:
        stats = await sync_documents(session, scanned, rag_mode="auto")
        assert stats["deleted"] == 0
        result = await session.execute(
            select(Document).where(Document.node_id == "node-1")
        )
        node_docs = result.scalars().all()
        assert [d.path for d in node_docs] == ["node/secret.md"]  # 节点文档幸存


async def test_hub_scan_does_not_delete_missing_local_rows_of_other_nodes(db):
    """扫描结果缺省某路径时,local 行删除仅限 local 作用域."""
    await _seed_document(db, "node-1", "same.md", "n")

    scanned = []  # hub 本机扫描为空
    async with db() as session:
        stats = await sync_documents(session, scanned, rag_mode="auto")
        result = await session.execute(
            select(Document).where(Document.node_id == "node-1")
        )
        assert len(result.scalars().all()) == 1  # 节点文档仍在


def test_scanner_paths_use_posix_separators(tmp_path):
    """Windows 下扫描路径不得混入反斜杠(URL 导航/查找一致性的前提)."""
    sub = tmp_path / "notes" / "web"
    sub.mkdir(parents=True)
    (sub / "a.md").write_text("hello", encoding="utf-8")
    (tmp_path / "root.md").write_text("hi", encoding="utf-8")

    docs = scan_knowledge_roots([tmp_path])
    paths = [d.path for d in docs]
    assert {"notes/web/a.md", "root.md"} == set(paths)
    assert all("\\" not in p for p in paths)


def test_scanner_keeps_hidden_root(tmp_path):
    """根目录本身是隐藏目录(如 .workbuddy-ai)时不应整根跳过,仅相对路径内的隐藏项跳过."""
    hidden_root = tmp_path / ".hidden-root"
    sub = hidden_root / "memory"
    sub.mkdir(parents=True)
    (sub / "2026-09-14.md").write_text("memo", encoding="utf-8")
    (hidden_root / ".dotfile.md").write_text("hidden", encoding="utf-8")

    docs = scan_knowledge_roots([hidden_root])
    paths = [d.path for d in docs]
    # 隐藏根自身下的内容纳入扫描;根内隐藏文件(.dotfile.md)仍跳过
    assert paths == ["memory/2026-09-14.md"]


def test_scanner_skips_nested_hidden_dirs(tmp_path):
    """根目录内的隐藏子目录/文件应跳过(原有行为保持)."""
    hidden = tmp_path / ".notes"
    hidden.mkdir()
    (hidden / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")

    docs = scan_knowledge_roots([tmp_path])
    assert [d.path for d in docs] == ["b.md"]