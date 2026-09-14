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


async def test_list_documents_default_full(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents", headers=admin_headers)
    assert resp.status_code == 200
    paths = {d["path"] for d in resp.json()}
    assert paths == {"docs/a.md", "docs/sub/b.md", "other.md"}


async def test_list_documents_filter_by_node(db, client, admin_headers):
    await _seed(db)
    resp = await client.get("/api/documents", params={"node_id": "node-1"}, headers=admin_headers)
    assert resp.status_code == 200
    paths = {d["path"] for d in resp.json()}
    assert paths == {"docs/a.md", "docs/sub/b.md"}
    # 其它节点文档不外泄
    assert "other.md" not in paths


async def test_list_documents_filter_local_node(db, client, admin_headers):
    """local 作为节点 ID 参与过滤(node_id='local' 为 hub 本机目录)."""
    await _seed(db)
    resp = await client.get("/api/documents", params={"node_id": "local"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---- dir 切片(懒加载契约) ----

async def test_tree_slice_root_one_level(db, client, admin_headers):
    """dir 传空串 → 根切片:只返回顶层目录占位/文件,不含更深层."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": ""}, headers=admin_headers)
    assert resp.status_code == 200
    tree = resp.json()
    assert tree == {"docs": {}}


async def test_tree_slice_dir_one_level(db, client, admin_headers):
    """dir=docs → 该目录一层子项:文件带 id,子目录 {} 占位,不含更深层."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": "docs"}, headers=admin_headers)
    tree = resp.json()
    assert "a.md" in tree and "sub" in tree
    assert tree["a.md"]["_path"] == "docs/a.md"
    assert isinstance(tree["a.md"]["id"], int)
    assert tree["sub"] == {}
    assert "b.md" not in tree  # 一层性


async def test_tree_slice_node_filter(db, client, admin_headers):
    """切片 + node 过滤:node-2 根切片只含自己的文档."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-2", "dir": ""}, headers=admin_headers)
    tree = resp.json()
    assert "other.md" in tree and "docs" not in tree


async def test_tree_slice_missing_dir(db, client, admin_headers):
    """不存在的目录 → 空 dict."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": "ghost"}, headers=admin_headers)
    assert resp.json() == {}


async def test_tree_slice_trailing_slash(db, client, admin_headers):
    """dir 尾斜杠归一(防前端误传 'docs/')."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": "docs/"}, headers=admin_headers)
    assert "a.md" in resp.json()


async def test_tree_slice_special_chars(db, client, admin_headers):
    """目录/文件名含 % _ 等 LIKE 特殊字符时切片仍精确."""
    async with db() as session:
        session.add(Document(
            node_id="node-1", path="docs/deep/100%_done.md", title="Done",
            hash="h-special", size=1, content="d", rag_status="indexed",
        ))
        await session.commit()
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": "docs/deep"}, headers=admin_headers)
    assert "100%_done.md" in resp.json()
    # 父目录切片不把 deep 目录误展成文件
    resp2 = await client.get("/api/documents/tree", params={"node_id": "node-1", "dir": "docs"}, headers=admin_headers)
    assert resp2.json()["deep"] == {}


async def test_tree_full_mode_leaves_carry_id(db, client, admin_headers):
    """全量模式叶子同样携带 id(协议一致)."""
    await _seed(db)
    resp = await client.get("/api/documents/tree", params={"node_id": "node-1"}, headers=admin_headers)
    tree = resp.json()
    assert isinstance(tree["docs"]["a.md"]["id"], int)
    assert isinstance(tree["docs"]["sub"]["b.md"]["id"], int)


# ---- documents?path= 精确解析 ----

async def test_list_documents_by_path(db, client, admin_headers):
    """path 精确匹配 + node 组合定位单文档(替代 Knowledge 页全量拉取)."""
    await _seed(db)
    resp = await client.get("/api/documents", params={"node_id": "node-1", "path": "docs/a.md"}, headers=admin_headers)
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["path"] == "docs/a.md"
    assert isinstance(docs[0]["id"], int)

    resp2 = await client.get("/api/documents", params={"node_id": "node-1", "path": "nope.md"}, headers=admin_headers)
    assert resp2.json() == []


async def test_list_documents_by_path_with_rag_status(db, client, admin_headers):
    """path + rag_status 组合过滤."""
    await _seed(db)
    resp = await client.get("/api/documents",
                            params={"node_id": "node-1", "path": "docs/sub/b.md", "rag_status": "excluded"},
                            headers=admin_headers)
    docs = resp.json()
    assert len(docs) == 1 and docs[0]["rag_status"] == "excluded"

    resp2 = await client.get("/api/documents",
                             params={"node_id": "node-1", "path": "docs/a.md", "rag_status": "excluded"},
                             headers=admin_headers)
    assert resp2.json() == []