"""文件树端点测试(GET /api/documents/tree).

覆盖:node_id 过滤 / 缺省全量 / 不存在节点返回空树 / 文件节点携带 rag_status。
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.services.auth import create_access_token, hash_password


@pytest_asyncio.fixture
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
    async with db() as session:
        session.add(User(username="admin", password_hash=hash_password("pw-123456"), role="admin"))
        await session.commit()
    token = create_access_token("admin", "admin")
    return {"Authorization": f"Bearer {token}"}


async def _seed(session_factory):
    async with session_factory() as session:
        session.add_all([
            Document(node_id="node-1", path="docs/a.md", title="A", hash="h1",
                     size=1, content="a", rag_status="indexed"),
            Document(node_id="node-1", path="docs/sub/b.md", title="B", hash="h2",
                     size=1, content="b", rag_status="excluded"),
            Document(node_id="node-2", path="other.md", title="Other", hash="h3",
                     size=1, content="o", rag_status="pending"),
        ])
        await session.commit()


async def test_tree_full_default(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents/tree", headers=admin_headers)
    assert resp.status_code == 200
    tree = resp.json()
    assert "docs" in tree and "other.md" in tree


async def test_tree_filter_by_node(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1"}, headers=admin_headers)
    tree = resp.json()
    # node-1 只有 docs/ 前缀,不含其他节点
    assert "other.md" not in tree
    assert "docs" in tree
    assert tree["docs"]["sub"]["b.md"]["_path"] == "docs/sub/b.md"


async def test_tree_missing_node_returns_empty(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "ghost"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_tree_files_carry_rag_status(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1"}, headers=admin_headers)
    tree = resp.json()
    assert tree["docs"]["a.md"]["_rag_status"] == "indexed"
    assert tree["docs"]["sub"]["b.md"]["_rag_status"] == "excluded"