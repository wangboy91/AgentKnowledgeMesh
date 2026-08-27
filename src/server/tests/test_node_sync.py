"""节点文档同步端点测试.

覆盖 PUT /api/nodes/{node_id}/documents 的：
- 鉴权（401 无效令牌 / 404 节点不存在）
- 增量入库（新增 / 更新 / 删除）
- 作用域隔离（不触及 local 或其他节点）
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


@pytest_asyncio.fixture
async def db():
    """提供独立的内存数据库并覆盖 get_session 依赖."""
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
    """基于内存数据库的应用客户端."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_node(session_factory, node_id, token):
    async with session_factory() as session:
        session.add(Node(id=node_id, name="test", platform="darwin", token=token))
        await session.commit()


async def _seed_document(session_factory, node_id, path, title="T", hash_="h", size=0, content=""):
    async with session_factory() as session:
        session.add(Document(
            node_id=node_id, path=path, title=title, hash=hash_, size=size, content=content,
        ))
        await session.commit()


async def _count_docs(session_factory, node_id):
    async with session_factory() as session:
        result = await session.execute(select(Document).where(Document.node_id == node_id))
        return result.scalars().all()


def _payload(docs):
    return {"documents": [
        {
            "path": d["path"],
            "title": d["title"],
            "hash": d["hash"],
            "size": d["size"],
            "content": d["content"],
        }
        for d in docs
    ]}


async def test_put_documents_create(db, client):
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 2, "content": "hi"}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "updated": 0, "deleted": 0}

    docs = await _count_docs(db, node_id)
    assert len(docs) == 1
    assert docs[0].node_id == node_id
    assert docs[0].content == "hi"


async def test_put_documents_update(db, client):
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", title="Old", hash_="h1", size=2, content="old")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "New", "hash": "h2", "size": 3, "content": "new"}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 1, "deleted": 0}

    docs = await _count_docs(db, node_id)
    assert len(docs) == 1
    assert docs[0].title == "New"
    assert docs[0].content == "new"


async def test_put_documents_delete(db, client):
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", hash_="h1")
    await _seed_document(db, node_id, "b.md", hash_="h2")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 0, "content": ""}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 1}

    docs = await _count_docs(db, node_id)
    assert {d.path for d in docs} == {"a.md"}


async def test_put_documents_scoping_isolated(db, client):
    """上传不应触及 local 或其他节点的文档."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, "local", "local.md", hash_="h-local")
    await _seed_document(db, "node-2", "other.md", hash_="h-other")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "own.md", "title": "Own", "hash": "h-own", "size": 0, "content": ""}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    own = await _count_docs(db, node_id)
    assert {d.path for d in own} == {"own.md"}

    local = await _count_docs(db, "local")
    assert {d.path for d in local} == {"local.md"}

    other = await _count_docs(db, "node-2")
    assert {d.path for d in other} == {"other.md"}


async def test_put_documents_invalid_token(db, client):
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 0, "content": ""}]),
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


async def test_put_documents_missing_node(db, client):
    resp = await client.put(
        "/api/nodes/ghost/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 0, "content": ""}]),
        headers={"Authorization": "Bearer whatever"},
    )
    assert resp.status_code == 404
