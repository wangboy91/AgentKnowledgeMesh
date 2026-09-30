"""文档来源标识(origin)与文件事件免疫测试.

覆盖 `2026-09-30-fix-document-persistence` 修复的两个已知问题(见 `docs/known-issues.md`):

- 问题 1:Hub 端编辑对「有对应磁盘文件」的文档是暂态的——会被 Hub 扫描(local 分支)
  或节点同步(节点分支)用磁盘内容覆盖回去;
- 问题 2:Hub / 智能体新建的文档会被 Hub 扫描删除。

以及确保 `file` 来源文档的既有行为(内容覆盖、消失即删)不因本次变更回归。

向量化默认关闭,故本文件不触达向量库。
"""

import pytest_asyncio
from sqlalchemy import inspect as sql_inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.nodes import NodeDocumentItem, _sync_node_documents
from app.db import Base
from app.models.document import Document
from app.services import document_writer
from app.services.indexer import sync_documents
from akm_shared.scanner import ScannedDocument


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


async def _seed(session_factory, *, node_id="local", path="a.md", content="disk",
                hash_="h-disk", origin="file"):
    async with session_factory() as session:
        session.add(Document(
            node_id=node_id, path=path, title=path, hash=hash_,
            size=len(content), content=content, origin=origin,
        ))
        await session.commit()


async def _get(session_factory, node_id, path):
    async with session_factory() as session:
        result = await session.execute(
            select(Document).where(Document.node_id == node_id, Document.path == path)
        )
        return result.scalar_one_or_none()


def _scanned(path="a.md", content="disk", hash_="h-disk"):
    return ScannedDocument(
        path=path, title=path, hash=hash_, size=len(content), content=content, source="kb",
    )


# ---- 写入口径:Hub 写入即转 agent ----------------------------------------


async def test_create_document_marks_agent(db):
    """新建文档来源为 agent(问题 2 的前提:不落盘的文档须由 Hub 持有权威)."""
    async with db() as session:
        doc = await document_writer.create_document(
            session, node_id="local", path="notes/new.md", content="# New\n\nbody"
        )
        assert doc.origin == "agent"
        assert doc.to_dict()["origin"] == "agent"


async def test_update_document_switches_to_agent(db):
    """编辑把 file 来源文档转为 agent(问题 1 的前提:编辑后不再被磁盘覆盖)."""
    await _seed(db, path="a.md", content="disk", hash_="h-disk", origin="file")
    async with db() as session:
        doc = (await session.execute(select(Document))).scalar_one()
        updated = await document_writer.update_document(session, doc, "# Edited\n\nnew")
        assert updated.origin == "agent"


async def test_update_document_keeps_agent_origin(db):
    """agent 文档再次被编辑仍为 agent(转换是单向的)."""
    await _seed(db, path="a.md", content="v1", hash_="h1", origin="agent")
    async with db() as session:
        doc = (await session.execute(select(Document))).scalar_one()
        updated = await document_writer.update_document(session, doc, "# v2\n\nbody")
        assert updated.origin == "agent"


# ---- Hub 扫描:只管理 file 来源 -------------------------------------------


async def test_hub_scan_keeps_agent_doc_missing_from_disk(db):
    """问题 2:agent 来源文档不因「磁盘上没有」被扫描删除."""
    await _seed(db, path="agent-note.md", origin="agent")
    async with db() as session:
        stats = await sync_documents(session, [], rag_mode="auto")
        assert stats["deleted"] == 0
    assert await _get(db, "local", "agent-note.md") is not None


async def test_hub_scan_does_not_overwrite_agent_doc(db):
    """问题 1(local 分支):agent 来源文档不被磁盘内容覆盖."""
    await _seed(db, path="a.md", content="agent version", hash_="h-agent", origin="agent")
    async with db() as session:
        stats = await sync_documents(
            session, [_scanned(content="disk version", hash_="h-disk")], rag_mode="auto"
        )
        assert stats["skipped"] == 1
        assert stats["updated"] == 0
    doc = await _get(db, "local", "a.md")
    assert doc.content == "agent version"
    assert doc.hash == "h-agent"


async def test_hub_scan_still_deletes_file_doc(db):
    """回归:file 来源文档消失仍被删除,且不影响同批其他文件."""
    await _seed(db, path="gone.md", origin="file")
    await _seed(db, path="kept.md", origin="file")
    async with db() as session:
        stats = await sync_documents(session, [_scanned(path="kept.md")], rag_mode="auto")
        assert stats["deleted"] == 1
    assert await _get(db, "local", "gone.md") is None
    assert await _get(db, "local", "kept.md") is not None


async def test_hub_scan_still_updates_file_doc(db):
    """回归:file 来源文档内容变化仍被更新,origin 保持 file."""
    await _seed(db, path="a.md", content="old", hash_="h-old", origin="file")
    async with db() as session:
        stats = await sync_documents(
            session, [_scanned(content="new", hash_="h-new")], rag_mode="auto"
        )
        assert stats["updated"] == 1
    doc = await _get(db, "local", "a.md")
    assert doc.content == "new"
    assert doc.origin == "file"


async def test_hub_scan_agent_and_file_coexist(db):
    """agent 与 file 混存时,各自的推导互不干扰."""
    await _seed(db, path="agent.md", origin="agent")
    await _seed(db, path="file.md", origin="file")
    async with db() as session:
        stats = await sync_documents(session, [], rag_mode="auto")
        assert stats["deleted"] == 1   # 仅 file.md
    assert await _get(db, "local", "agent.md") is not None
    assert await _get(db, "local", "file.md") is None


# ---- 节点同步:agent 来源免疫 ---------------------------------------------


async def test_node_sync_skips_agent_doc_full_content(db):
    """问题 1(节点分支):agent 来源文档不被节点带全文的推送覆盖."""
    await _seed(db, node_id="node-1", path="a.md", content="agent version",
                hash_="h-agent", origin="agent")
    docs = [NodeDocumentItem(path="a.md", title="A", hash="h-disk",
                             size=12, content="disk version")]
    async with db() as session:
        stats, _ = await _sync_node_documents(
            session, "node-1", docs, [], False, "manual", False
        )
    assert stats["updated"] == 0
    assert stats["skipped"] == [{"path": "a.md", "reason": "agent origin"}]
    doc = await _get(db, "node-1", "a.md")
    assert doc.content == "agent version"
    assert doc.hash == "h-agent"


async def test_node_sync_agent_doc_hash_only_not_rejected(db):
    """关键约束:agent 来源的 hash-only 不一致条目须跳过而非 rejected.

    计入 rejected 会让节点把该路径移出本地快照、下轮带全文重传、再被拒,
    形成每轮重传且永不收敛的循环。
    """
    await _seed(db, node_id="node-1", path="a.md", content="agent version",
                hash_="h-agent", origin="agent")
    docs = [NodeDocumentItem(path="a.md", title="A", hash="h-disk", size=12)]
    async with db() as session:
        stats, _ = await _sync_node_documents(
            session, "node-1", docs, [], False, "manual", False
        )
    assert stats["rejected"] == []
    assert stats["skipped"] == [{"path": "a.md", "reason": "agent origin"}]


async def test_node_sync_deletions_keep_agent_doc(db):
    """agent 来源文档不被显式 deletions 删除,file 来源仍被删除."""
    await _seed(db, node_id="node-1", path="agent.md", origin="agent")
    await _seed(db, node_id="node-1", path="file.md", origin="file")
    async with db() as session:
        stats, _ = await _sync_node_documents(
            session, "node-1", [], ["agent.md", "file.md"], False, "manual", False
        )
    assert stats["deleted"] == 1
    assert await _get(db, "node-1", "agent.md") is not None
    assert await _get(db, "node-1", "file.md") is None


async def test_node_sync_implicit_delete_keeps_agent_doc(db):
    """旧版全量推送(列表缺失即删)同样不删 agent 来源文档."""
    await _seed(db, node_id="node-1", path="agent.md", origin="agent")
    async with db() as session:
        stats, _ = await _sync_node_documents(
            session, "node-1", [], [], True, "manual", False
        )
    assert stats["deleted"] == 0
    assert await _get(db, "node-1", "agent.md") is not None


async def test_node_sync_still_updates_file_doc(db):
    """回归:file 来源文档仍由节点同步更新,origin 保持 file."""
    await _seed(db, node_id="node-1", path="a.md", content="old",
                hash_="h-old", origin="file")
    docs = [NodeDocumentItem(path="a.md", title="A", hash="h-new", size=3, content="new")]
    async with db() as session:
        stats, _ = await _sync_node_documents(
            session, "node-1", docs, [], False, "manual", False
        )
    assert stats["updated"] == 1
    assert stats["skipped"] == []
    doc = await _get(db, "node-1", "a.md")
    assert doc.content == "new"
    assert doc.origin == "file"


async def test_node_sync_agent_doc_does_not_leak_to_local(db):
    """作用域隔离:agent 免疫逻辑不改变「只动本节点文档」的既有约束."""
    await _seed(db, node_id="local", path="a.md", content="local version",
                hash_="h-local", origin="agent")
    docs = [NodeDocumentItem(path="a.md", title="A", hash="h-disk",
                             size=12, content="disk version")]
    async with db() as session:
        await _sync_node_documents(session, "node-1", docs, [], False, "manual", False)
    doc = await _get(db, "local", "a.md")
    assert doc.content == "local version"


# ---- 存量库迁移 -----------------------------------------------------------


async def test_migrate_adds_origin_column_defaulting_to_file(tmp_path, monkeypatch):
    """存量库补 origin 列后,旧行一律为 file —— 与迁移前行为一致."""
    import app.db as db_module

    db_file = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    async with engine.begin() as conn:
        # 旧版 documents 表(无 origin 列)
        await conn.execute(text(
            "CREATE TABLE documents ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "node_id VARCHAR(36),"
            "path VARCHAR(1024) NOT NULL,"
            "title VARCHAR(512) NOT NULL,"
            "hash VARCHAR(64) NOT NULL,"
            "size INTEGER NOT NULL,"
            "tags TEXT,"
            "content TEXT,"
            "rag_status VARCHAR(16) NOT NULL DEFAULT 'indexed',"
            "created_at DATETIME,"
            "updated_at DATETIME)"
        ))
        await conn.execute(text(
            "INSERT INTO documents (node_id, path, title, hash, size)"
            " VALUES ('local', 'legacy.md', 'Legacy', 'h', 1)"
        ))

    monkeypatch.setattr(db_module, "engine", engine)
    await db_module._migrate_columns()

    async with engine.connect() as conn:
        columns = await conn.run_sync(
            lambda c: {x["name"] for x in sql_inspect(c).get_columns("documents")}
        )
        assert "origin" in columns
        assert (await conn.execute(text("SELECT origin FROM documents"))).scalar_one() == "file"
    await engine.dispose()
