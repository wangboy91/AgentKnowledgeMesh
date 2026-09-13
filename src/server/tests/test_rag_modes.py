"""RAG 同步模式单测.

覆盖:
- 设置 API(默认 auto / admin 切换 / 切 auto 后台补齐非 excluded)
- scan 模式联动(auto 派发向量 / manual 置 excluded 无向量操作)
- 全量索引跳过 excluded;检索排除集(语义不可见)
- 文档级勾选状态机(加入 pending→indexed / 移出 excluded+删向量)与批量
- 列表 rag_status 携带与过滤
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


class _FakeResult:
    def all(self):
        return []


class _FakeSession:
    async def execute(self, *a, **k):
        return _FakeResult()


class _FakeCtx:
    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *a):
        return False


@pytest_asyncio.fixture(autouse=True)
def stub_vector_store(db, monkeypatch):
    """拦截后台向量维护;pending→indexed 回写复用内存库(不触真实库)."""
    calls = {"add": [], "delete": []}
    monkeypatch.setattr(
        "app.services.rag.vector_store.add_document",
        lambda **kw: calls["add"].append(kw),
    )
    monkeypatch.setattr(
        "app.services.rag.vector_store.delete_document",
        lambda doc_id: calls["delete"].append(doc_id),
    )
    # sync._mark_indexed 的后台 DB 会话指向内存库,实现真实状态回写
    monkeypatch.setattr("app.db.async_session", lambda: db())
    return calls


@pytest_asyncio.fixture(autouse=True)
async def db():
    """提供独立内存数据库并覆盖 get_session 依赖."""
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


@pytest_asyncio.fixture
async def viewer_headers(db):
    from app.models.user import User
    from app.services.auth import create_access_token, hash_password

    async with db() as session:
        session.add(User(username="viewer1", password_hash=hash_password("pw-123456"), role="viewer"))
        await session.commit()

    token = create_access_token("viewer1", "viewer")
    return {"Authorization": f"Bearer {token}"}


async def _seed_document(session_factory, path, content="content", rag_status="indexed"):
    async with session_factory() as session:
        session.add(Document(
            node_id="local", path=path, title=path, hash=f"h-{path}", size=len(content),
            content=content, rag_status=rag_status,
        ))
        await session.commit()


async def _docs(session_factory, rag_status=None):
    async with session_factory() as session:
        stmt = select(Document)
        if rag_status:
            stmt = stmt.where(Document.rag_status == rag_status)
        return [d.path for d in (await session.execute(stmt)).scalars().all()]


# ---- 1.3 设置 API 与模式切换 ----

async def test_settings_default_auto(client, admin_headers):
    resp = await client.get("/api/settings", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {"rag_sync_mode": "auto"}


async def test_settings_switch_manual_invalid_rejected(db, client, admin_headers):
    resp = await client.put(
        "/api/settings", json={"rag_sync_mode": "bogus"}, headers=admin_headers,
    )
    assert resp.status_code == 400


async def test_settings_switch_manual_keeps_vectors(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", rag_status="indexed")

    resp = await client.put(
        "/api/settings", json={"rag_sync_mode": "manual"}, headers=admin_headers,
    )
    assert resp.status_code == 200
    # 切换 manual:既有向量不受影响(无任何向量操作)
    assert stub_vector_store["add"] == [] and stub_vector_store["delete"] == []


async def test_settings_switch_back_auto_backfills(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="AAA", rag_status="indexed")
    await _seed_document(db, "skip.md", content="BBB", rag_status="excluded")

    await client.put("/api/settings", json={"rag_sync_mode": "manual"}, headers=admin_headers)
    stub_vector_store["add"].clear()

    resp = await client.put("/api/settings", json={"rag_sync_mode": "auto"}, headers=admin_headers)
    assert resp.status_code == 200

    # 后台补齐:仅非 excluded 文档被向量化
    added_paths = {a["path"] for a in stub_vector_store["add"]}
    assert added_paths == {"a.md"}


# ---- 2.3 scan 模式联动 ----

def _scanned_docs_stub():
    from akm_shared.scanner import ScannedDocument

    return [
        ScannedDocument(path="s1.md", title="S1", hash="h1", size=3, content="one", source="kb"),
        ScannedDocument(path="s2.md", title="S2", hash="h2", size=3, content="two", source="kb"),
    ]


async def _scanned_docs():
    return _scanned_docs_stub()


async def test_scan_auto_vectors_created(monkeypatch, db, client, admin_headers, stub_vector_store):
    monkeypatch.setattr(
        "app.services.scanner.scan_knowledge_root", _scanned_docs,
    )

    resp = await client.post("/api/documents/scan", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["created"] == 2
    added_paths = {a["path"] for a in stub_vector_store["add"]}
    assert added_paths == {"s1.md", "s2.md"}


async def test_scan_manual_excludes_no_vectors(monkeypatch, db, client, admin_headers, stub_vector_store):
    await client.put("/api/settings", json={"rag_sync_mode": "manual"}, headers=admin_headers)
    monkeypatch.setattr("app.services.scanner.scan_knowledge_root", _scanned_docs)

    resp = await client.post("/api/documents/scan", headers=admin_headers)

    assert resp.status_code == 200
    assert stub_vector_store["add"] == []
    assert len(await _docs(db, rag_status="excluded")) == 2


# ---- 3.1 全量索引跳过 excluded / 检索排除集 ----

async def test_rag_index_skips_excluded(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "keep.md", content="keep content")
    await _seed_document(db, "skip.md", content="skip content", rag_status="excluded")

    resp = await client.post("/api/rag/index", headers=admin_headers)

    assert resp.status_code == 200
    added_paths = {a["path"] for a in stub_vector_store["add"]}
    assert added_paths == {"keep.md"}


async def test_semantic_search_excludes_non_indexed(monkeypatch, db, client, admin_headers):
    """语义检索把 rag_status != indexed 的文档传入 excluded 排除集."""
    await _seed_document(db, "excluded.md", content="secret", rag_status="excluded")
    await _seed_document(db, "pending.md", content="queued", rag_status="pending")

    captured = {}
    from app.services.rag import vector_store

    def fake_hybrid(query, limit=5, node_id=None, excluded_doc_ids=None):
        captured["excluded"] = excluded_doc_ids
        return []

    monkeypatch.setattr(vector_store, "search_hybrid", fake_hybrid)

    resp = await client.get("/api/rag/search", params={"q": "secret"}, headers=admin_headers)

    assert resp.status_code == 200
    # excluded + pending 均不可见
    assert captured["excluded"] is not None
    assert len(captured["excluded"]) == 2


# ---- 3.2 文档级勾选状态机 / 批量 ----

async def test_document_rag_enable_machine(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="AAA", rag_status="excluded")

    resp = await client.put(
        "/api/documents/1/rag", json={"enabled": True}, headers=admin_headers,
    )
    assert resp.status_code == 200
    # 后台完成:add 一次 + 回写 indexed(pending 路径)
    assert [a["path"] for a in stub_vector_store["add"]] == ["a.md"]
    assert [d for d in await _docs(db, rag_status="indexed")] == ["a.md"]


async def test_document_rag_disable_cleans_vectors(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="AAA", rag_status="indexed")

    resp = await client.put(
        "/api/documents/1/rag", json={"enabled": False}, headers=admin_headers,
    )
    assert resp.status_code == 200

    assert stub_vector_store["delete"] == [1]
    assert [d for d in await _docs(db, rag_status="excluded")] == ["a.md"]


async def test_document_rag_batch(db, client, admin_headers, stub_vector_store):
    await _seed_document(db, "a.md", content="A", rag_status="excluded")
    await _seed_document(db, "b.md", content="B", rag_status="excluded")

    resp = await client.post(
        "/api/documents/rag/batch",
        json={"doc_ids": [1, 2], "enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"updated": 2}
    assert {a["path"] for a in stub_vector_store["add"]} == {"a.md", "b.md"}


async def test_document_rag_viewer_forbidden(db, client, viewer_headers):
    resp = await client.put("/api/documents/1/rag", json={"enabled": True}, headers=viewer_headers)
    assert resp.status_code == 403


# ---- 3.3 列表携带 rag_status 并支持过滤 ----

async def test_list_documents_carries_rag_status(db, client, admin_headers):
    await _seed_document(db, "a.md", content="A", rag_status="indexed")
    await _seed_document(db, "b.md", content="B", rag_status="excluded")

    resp = await client.get("/api/documents", headers=admin_headers)

    assert resp.status_code == 200
    by_path = {d["path"]: d for d in resp.json()}
    assert by_path["a.md"]["rag_status"] == "indexed"
    assert by_path["b.md"]["rag_status"] == "excluded"


async def test_list_documents_filters_by_rag_status(db, client, admin_headers):
    await _seed_document(db, "a.md", content="A", rag_status="indexed")
    await _seed_document(db, "b.md", content="B", rag_status="excluded")

    resp = await client.get("/api/documents", params={"rag_status": "excluded"}, headers=admin_headers)

    assert [d["path"] for d in resp.json()] == ["b.md"]