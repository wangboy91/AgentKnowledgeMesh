"""向量化总开关单测.

覆盖「向量化默认关闭」这一产品形态的完整行为面:
- 开关默认关闭;开启先建表(失败即拒绝开启);关闭不清理既有向量
- 关闭时:扫描/创建/更新/节点上传一律 not_indexed 且无向量操作
- 关闭时:全量索引与"加入 RAG"返回 409,"移出 RAG"仍放行
- 关闭时:语义检索/上下文降级为关键词(mode=keyword,不触向量库);stats 不连向量库
- excluded 粘性:用户显式移出的文档不因内容变更被拉回
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models.document import Document
from app.models.node import Node
from app.models.settings import AppSetting


@pytest_asyncio.fixture(autouse=True)
def stub_vector_store(db, monkeypatch):
    """拦截向量库接口与建表动作,避免触达真实 PG / 嵌入 API."""
    calls = {"add": [], "delete": [], "hybrid": [], "stats": 0, "init": 0}

    monkeypatch.setattr(
        "app.services.rag.vector_store.add_document",
        lambda **kw: calls["add"].append(kw),
    )
    monkeypatch.setattr(
        "app.services.rag.vector_store.delete_document",
        lambda doc_id: calls["delete"].append(doc_id),
    )

    def _hybrid(**kw):
        calls["hybrid"].append(kw)
        return []

    monkeypatch.setattr("app.services.rag.vector_store.search_hybrid", _hybrid)

    def _stats():
        calls["stats"] += 1
        return {"total_chunks": 42}

    monkeypatch.setattr("app.services.rag.vector_store.get_stats", _stats)

    def _init():
        calls["init"] += 1

    monkeypatch.setattr("app.api.settings._init_vector_store_sync", _init)
    monkeypatch.setattr("app.db.async_session", lambda: db())
    return calls


@pytest_asyncio.fixture(autouse=True)
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    yield session_factory

    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_headers(db):
    from app.models.user import User
    from app.services.auth import create_access_token, hash_password

    async with db() as session:
        session.add(User(username="admin", password_hash=hash_password("pw-123456"), role="admin"))
        await session.commit()

    token = create_access_token("admin", "admin")
    return {"Authorization": f"Bearer {token}"}


async def _set_setting(session_factory, key, value):
    async with session_factory() as session:
        row = await session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=value))
        else:
            row.value = value
        await session.commit()


async def _seed_document(session_factory, path, content="content", rag_status="not_indexed"):
    async with session_factory() as session:
        session.add(Document(
            node_id="local", path=path, title=path, hash=f"h-{path}", size=len(content),
            content=content, rag_status=rag_status,
        ))
        await session.commit()


async def _status(session_factory, path):
    async with session_factory() as session:
        result = await session.execute(select(Document).where(Document.path == path))
        doc = result.scalar_one_or_none()
        return doc.rag_status if doc else None


# ---- 开关本身 ----

async def test_switch_defaults_off(client, admin_headers):
    resp = await client.get("/api/settings", headers=admin_headers)
    assert resp.json()["vectorization_enabled"] is False


async def test_enable_initializes_vector_store(db, client, admin_headers, stub_vector_store):
    resp = await client.put(
        "/api/settings", json={"vectorization_enabled": True}, headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["vectorization_enabled"] is True
    assert stub_vector_store["init"] == 1


async def test_enable_failure_keeps_switch_off(db, client, admin_headers, monkeypatch):
    def _boom():
        raise RuntimeError("pgvector unavailable")

    monkeypatch.setattr("app.api.settings._init_vector_store_sync", _boom)

    resp = await client.put(
        "/api/settings", json={"vectorization_enabled": True}, headers=admin_headers,
    )
    assert resp.status_code == 500

    resp = await client.get("/api/settings", headers=admin_headers)
    assert resp.json()["vectorization_enabled"] is False


async def test_disable_keeps_existing_vectors(db, client, admin_headers, stub_vector_store):
    await _set_setting(db, "vectorization_enabled", "true")

    resp = await client.put(
        "/api/settings", json={"vectorization_enabled": False}, headers=admin_headers,
    )
    assert resp.status_code == 200
    # 关闭不清理既有向量(重新开启即可复用)
    assert stub_vector_store["add"] == [] and stub_vector_store["delete"] == []


# ---- 关闭时的入库行为 ----

async def test_scan_while_disabled_marks_not_indexed(monkeypatch, db, client, admin_headers, stub_vector_store):
    from akm_shared.scanner import ScannedDocument

    async def _scanned():
        return [ScannedDocument(path="s1.md", title="S1", hash="h1", size=3, content="one", source="kb")]

    monkeypatch.setattr("app.services.scanner.scan_knowledge_root", _scanned)

    resp = await client.post("/api/documents/scan", headers=admin_headers)

    assert resp.status_code == 200
    assert stub_vector_store["add"] == []
    assert await _status(db, "s1.md") == "not_indexed"


async def test_create_document_while_disabled(db, client, admin_headers, stub_vector_store):
    resp = await client.post(
        "/api/documents",
        json={"path": "new.md", "title": "New", "content": "hello"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["rag_status"] == "not_indexed"
    assert stub_vector_store["add"] == []


async def test_update_document_while_disabled(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="old", rag_status="indexed")

    resp = await client.put("/api/documents/1", json={"content": "new"}, headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["rag_status"] == "not_indexed"
    assert stub_vector_store["add"] == []


async def test_node_upload_while_disabled(db, client, stub_vector_store):
    async with db() as session:
        session.add(Node(id="node-1", name="n", platform="win", token="tok-1"))
        await session.commit()

    resp = await client.put(
        "/api/nodes/node-1/documents",
        json={"documents": [
            {"path": "a.md", "title": "A", "hash": "h1", "size": 2, "content": "hi"},
        ], "deletions": []},
        headers={"Authorization": "Bearer tok-1"},
    )
    assert resp.status_code == 200
    assert stub_vector_store["add"] == []

    async with db() as session:
        result = await session.execute(select(Document).where(Document.path == "a.md"))
        assert result.scalar_one().rag_status == "not_indexed"


# ---- 关闭时的手动向量化入口 ----

async def test_rag_index_conflicts_when_disabled(db, client, admin_headers):
    resp = await client.post("/api/rag/index", headers=admin_headers)
    assert resp.status_code == 409


async def test_document_rag_enable_conflicts_when_disabled(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="A")

    resp = await client.put("/api/documents/1/rag", json={"enabled": True}, headers=admin_headers)
    assert resp.status_code == 409
    assert stub_vector_store["add"] == []
    assert await _status(db, "a.md") == "not_indexed"


async def test_document_rag_disable_allowed_when_disabled(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="A", rag_status="indexed")

    resp = await client.put("/api/documents/1/rag", json={"enabled": False}, headers=admin_headers)

    assert resp.status_code == 200
    assert await _status(db, "a.md") == "excluded"
    assert stub_vector_store["delete"] == [1]


async def test_rag_batch_enable_conflicts_when_disabled(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="A")

    resp = await client.post(
        "/api/documents/rag/batch",
        json={"doc_ids": [1], "enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 409


# ---- 关闭时的检索降级 ----

async def test_semantic_search_degrades_to_keyword(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "hit.md", content="agent knowledge mesh")

    resp = await client.get("/api/rag/search", params={"q": "agent"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "keyword"
    assert body["count"] == 1
    assert body["results"][0]["path"] == "hit.md"
    # 降级路径不访问向量库
    assert stub_vector_store["hybrid"] == []


async def test_rag_context_degrades_to_keyword(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "hit.md", content="agent knowledge mesh")

    resp = await client.get("/api/rag/context", params={"q": "agent"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "keyword"
    assert body["count"] == 1
    assert body["documents"][0]["title"] == "hit.md"
    assert stub_vector_store["hybrid"] == []


async def test_stats_reports_switch_without_touching_vector_db(db, client, admin_headers, stub_vector_store):
    resp = await client.get("/api/rag/stats", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json() == {"total_chunks": 0, "vectorization_enabled": False}
    assert stub_vector_store["stats"] == 0


# ---- excluded 粘性 ----

async def test_excluded_sticky_across_content_change(monkeypatch, db, client, admin_headers, stub_vector_store):
    """向量化开启 + auto 时,用户显式移出的文档不因文件变更被拉回向量库."""
    await _set_setting(db, "vectorization_enabled", "true")
    await _set_setting(db, "rag_sync_mode", "auto")
    await _seed_document(db, "keep.md", content="old", rag_status="excluded")

    from akm_shared.scanner import ScannedDocument

    async def _scanned():
        return [ScannedDocument(
            path="keep.md", title="Keep", hash="h-new", size=3, content="new", source="kb",
        )]

    monkeypatch.setattr("app.services.scanner.scan_knowledge_root", _scanned)

    resp = await client.post("/api/documents/scan", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
    assert await _status(db, "keep.md") == "excluded"
    assert stub_vector_store["add"] == []
