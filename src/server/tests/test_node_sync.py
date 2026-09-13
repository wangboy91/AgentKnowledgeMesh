"""节点文档同步端点测试.

覆盖 PUT /api/nodes/{node_id}/documents 的：
- 鉴权（401 无效令牌 / 404 节点不存在）
- 增量入库（新增 / 更新 / 删除）
- hash-first 三分支（带全文入库 / 无全文哈希一致忽略 / 无全文不一致记 rejected）
- 显式 deletions 删除与新协议关闭隐式缺失删除
- rejected 条目带全文重传后入库
- 作用域隔离（不触及 local 或其他节点）
- 向量索引派发（created/updated 嵌入、哈希未变跳过、deleted 清理）
以及 DELETE /api/nodes/{node_id} 的向量级联清理。
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


@pytest_asyncio.fixture(autouse=True)
def stub_vector_store(monkeypatch):
    """拦截后台向量维护（替换 vector_store 接口），避免测试触达真实 PG / 嵌入 API.

    记录 add_document / delete_document 的调用参数，供派发语义断言。
    """
    calls = {"add": [], "delete": []}
    monkeypatch.setattr(
        "app.services.rag.vector_store.add_document",
        lambda **kw: calls["add"].append(kw),
    )
    monkeypatch.setattr(
        "app.services.rag.vector_store.delete_document",
        lambda doc_id: calls["delete"].append(doc_id),
    )
    return calls


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


@pytest_asyncio.fixture
async def admin_headers(db):
    """在测试库中创建管理员账号并返回其 JWT 鉴权头."""
    from app.models.user import User
    from app.services.auth import create_access_token, hash_password

    async with db() as session:
        session.add(User(username="admin", password_hash=hash_password("pw-123456"), role="admin"))
        await session.commit()

    token = create_access_token("admin", "admin")
    return {"Authorization": f"Bearer {token}"}


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
    """旧版全量推送 payload(全部含 content、无 deletions 字段)."""
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


def _hash_only(path, title, hash_, size=0):
    """hash-first 未变更条目(不带 content)."""
    return {"path": path, "title": title, "hash": hash_, "size": size}


async def test_put_documents_create(db, client):
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 2, "content": "hi"}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "updated": 0, "deleted": 0, "rejected": []}

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
    assert resp.json() == {"created": 0, "updated": 1, "deleted": 0, "rejected": []}

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
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 1, "rejected": []}

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


async def test_put_documents_dispatches_vector_upsert(db, client, stub_vector_store):
    """created/updated 文档派发后台嵌入，哈希未变的文档不重复嵌入."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "same.md", hash_="h1", content="same")
    await _seed_document(db, node_id, "chg.md", hash_="old", content="old")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([
            {"path": "same.md", "title": "Same", "hash": "h1", "size": 4, "content": "same"},
            {"path": "chg.md", "title": "Changed", "hash": "new", "size": 3, "content": "new"},
            {"path": "new.md", "title": "New", "hash": "h-new", "size": 3, "content": "new"},
        ]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 1, "updated": 1, "deleted": 0, "rejected": []}

    # 后台任务在响应周期内执行（ASGITransport 等待完整 ASGI 调用）
    added = {a["path"] for a in stub_vector_store["add"]}
    assert added == {"chg.md", "new.md"}  # same.md 哈希未变，不嵌入
    assert all(a["node_id"] == node_id for a in stub_vector_store["add"])
    assert stub_vector_store["delete"] == []


async def test_put_documents_dispatches_vector_delete(db, client, stub_vector_store):
    """本次同步删除的文档派发后台向量清理."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "keep.md", hash_="h1")
    await _seed_document(db, node_id, "gone.md", hash_="h2")

    docs = await _count_docs(db, node_id)
    gone_id = next(d.id for d in docs if d.path == "gone.md")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "keep.md", "title": "Keep", "hash": "h1", "size": 0, "content": ""}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 1, "rejected": []}

    assert stub_vector_store["delete"] == [gone_id]
    assert stub_vector_store["add"] == []


async def test_put_documents_no_changes_no_dispatch(db, client, stub_vector_store):
    """无增量时（哈希全未变）不派发任何向量操作."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", hash_="h1")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json=_payload([{"path": "a.md", "title": "A", "hash": "h1", "size": 0, "content": ""}]),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 0, "rejected": []}

    assert stub_vector_store["add"] == []
    assert stub_vector_store["delete"] == []


async def test_put_documents_hash_only_mismatch_rejected(db, client, stub_vector_store):
    """无全文且哈希不一致:计入 rejected(含原因),不入库,不派发向量操作."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", title="Old", hash_="h1", content="old")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("a.md", "A", "h2")]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "created": 0, "updated": 0, "deleted": 0,
        "rejected": [{"path": "a.md", "reason": "hash mismatch"}],
    }

    docs = await _count_docs(db, node_id)
    assert len(docs) == 1
    assert docs[0].hash == "h1"  # 库中原样保留,等待节点带全文重传
    assert docs[0].content == "old"
    assert stub_vector_store["add"] == []
    assert stub_vector_store["delete"] == []


async def test_put_documents_hash_only_missing_path_rejected(db, client, stub_vector_store):
    """无全文且路径不存在:计入 rejected(path not found)."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("ghost.md", "Ghost", "h1")]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "created": 0, "updated": 0, "deleted": 0,
        "rejected": [{"path": "ghost.md", "reason": "path not found"}],
    }
    assert await _count_docs(db, node_id) == []


async def test_put_documents_hash_only_unchanged_ignored(db, client, stub_vector_store):
    """无全文且库中哈希一致:忽略,不产生写操作与向量操作."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", title="A", hash_="h1", size=2, content="hi")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("a.md", "A", "h1", 2)]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 0, "rejected": []}

    docs = await _count_docs(db, node_id)
    assert len(docs) == 1
    assert docs[0].content == "hi"
    assert stub_vector_store["add"] == []
    assert stub_vector_store["delete"] == []


async def test_put_documents_deletions_field(db, client, stub_vector_store):
    """显式 deletions 删除对应文档并派发向量清理."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", hash_="h1")
    await _seed_document(db, node_id, "b.md", hash_="h2")

    docs = await _count_docs(db, node_id)
    b_id = next(d.id for d in docs if d.path == "b.md")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("a.md", "A", "h1")], "deletions": ["b.md"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 1, "rejected": []}

    assert {d.path for d in await _count_docs(db, node_id)} == {"a.md"}
    assert stub_vector_store["delete"] == [b_id]
    assert stub_vector_store["add"] == []


async def test_put_documents_new_protocol_no_implicit_delete(db, client, stub_vector_store):
    """新协议(显式携带 deletions 字段)关闭隐式缺失删除:未提及的路径保留."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", hash_="h1")
    await _seed_document(db, node_id, "b.md", hash_="h2")
    await _seed_document(db, node_id, "c.md", hash_="h3")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("a.md", "A", "h1")], "deletions": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 0, "rejected": []}

    # b.md/c.md 未出现在 documents 且 deletions 为空 → 不删除
    assert {d.path for d in await _count_docs(db, node_id)} == {"a.md", "b.md", "c.md"}
    assert stub_vector_store["delete"] == []


async def test_put_documents_rejected_retransmit_roundtrip(db, client, stub_vector_store):
    """rejected 条目下轮带全文重传:先拒绝,再上传后成功入库(补传闭环)."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", title="Old", hash_="h1", content="old")

    # 第一轮:节点仅报 hash(与库不一致)→ rejected
    resp1 = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [_hash_only("a.md", "A", "h2")], "deletions": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["rejected"] == [{"path": "a.md", "reason": "hash mismatch"}]

    # 第二轮:节点携带全文重传 → 入库成功并派发向量嵌入
    resp2 = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [
            {"path": "a.md", "title": "A", "hash": "h2", "size": 3, "content": "new"}
        ], "deletions": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json() == {"created": 0, "updated": 1, "deleted": 0, "rejected": []}

    docs = await _count_docs(db, node_id)
    assert len(docs) == 1
    assert docs[0].hash == "h2"
    assert docs[0].content == "new"
    assert {a["path"] for a in stub_vector_store["add"]} == {"a.md"}


async def test_put_documents_deletions_scoped(db, client, stub_vector_store):
    """deletions 作用域隔离:只删本节点名下路径,不触及 local 或其他节点."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, "local", "local.md", hash_="h-local")
    await _seed_document(db, "node-2", "other.md", hash_="h-other")

    resp = await client.put(
        f"/api/nodes/{node_id}/documents",
        json={"documents": [], "deletions": ["local.md", "other.md"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 0, "updated": 0, "deleted": 0, "rejected": []}

    assert {d.path for d in await _count_docs(db, "local")} == {"local.md"}
    assert {d.path for d in await _count_docs(db, "node-2")} == {"other.md"}
    assert stub_vector_store["delete"] == []


async def test_delete_node_cascades_vector_cleanup(db, client, stub_vector_store, admin_headers):
    """删除节点级联清理其全部文档的向量分块."""
    node_id, token = "node-1", "tok-1"
    await _seed_node(db, node_id, token)
    await _seed_document(db, node_id, "a.md", hash_="h1")
    await _seed_document(db, node_id, "b.md", hash_="h2")

    docs = await _count_docs(db, node_id)
    expected_ids = {d.id for d in docs}

    resp = await client.delete(f"/api/nodes/{node_id}", headers=admin_headers)
    assert resp.status_code == 200

    assert set(stub_vector_store["delete"]) == expected_ids
    assert stub_vector_store["add"] == []
    assert await _count_docs(db, node_id) == []
