"""文档写入口径与节点作用域测试(智能体写回).

覆盖:
- REST 写端点:节点凭证归属本节点、跨节点 403、`(node_id, path)` 唯一性
- 写入口径单源:标题提取、SHA256 / 字节大小、`excluded` 粘性、PathConflict
- MCP 写工具:成功文案、冲突 / 不存在 / 缺参数

向量化默认关闭,故写回文档 `rag_status` 为 `not_indexed`、不派发向量操作,
测试不触达向量库。
"""

import hashlib

import mcp.types as types
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import Node, User
from app.models.document import Document
from app.services.auth import create_access_token, hash_password

CONTENT = "# Alpha\n\nbody"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield factory
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def principals(db):
    async with db() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("pw"), role="admin"),
                User(username="viewer", password_hash=hash_password("pw"), role="viewer"),
                Node(id="node-1", name="n1", platform="win", token="1" * 32),
                Node(id="node-2", name="n2", platform="win", token="2" * 32),
            ]
        )
        await session.commit()
    return {
        "admin": {"Authorization": "Bearer " + create_access_token("admin", "admin")},
        "viewer": {"Authorization": "Bearer " + create_access_token("viewer", "viewer")},
        "node1": {"Authorization": "Bearer " + "1" * 32},
        "node2": {"Authorization": "Bearer " + "2" * 32},
    }


async def _create(client, headers, path="kb/a.md", content=CONTENT, title="Alpha"):
    return await client.post(
        "/api/documents",
        json={"path": path, "title": title, "content": content},
        headers=headers,
    )


# ---------- 创建:归属与唯一性 ----------


async def test_admin_create_defaults_to_local(db, client, principals):
    resp = await _create(client, principals["admin"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["node_id"] == "local"
    assert body["hash"] == hashlib.sha256(CONTENT.encode()).hexdigest()
    assert body["size"] == len(CONTENT.encode())


async def test_node_create_owned_by_node(db, client, principals):
    """节点凭证创建的文档归属该节点(不接受请求体指定)."""
    resp = await _create(client, principals["node1"])
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "node-1"


async def test_create_conflict_same_scope(db, client, principals):
    assert (await _create(client, principals["node1"])).status_code == 200
    resp = await _create(client, principals["node1"])
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Document already exists at this path"


async def test_create_same_path_other_node_ok(db, client, principals):
    """不同 node_id 的同名路径可共存(唯一性口径为 (node_id, path))."""
    assert (await _create(client, principals["node1"])).status_code == 200
    resp = await _create(client, principals["node2"])
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "node-2"


async def test_create_local_conflict_is_scoped_to_local(db, client, principals):
    """admin 建的 local 文档不阻塞节点建同名路径."""
    assert (await _create(client, principals["admin"])).status_code == 200
    assert (await _create(client, principals["node1"])).status_code == 200


async def test_viewer_create_forbidden(db, client, principals):
    resp = await _create(client, principals["viewer"])
    assert resp.status_code == 403


async def test_node_cannot_scan(db, client, principals):
    """节点凭证的写权限仅限于文档端点,扫描仍 403."""
    resp = await client.post("/api/documents/scan", headers=principals["node1"])
    assert resp.status_code == 403


# ---------- 更新:作用域 ----------


async def test_node_update_own_document(db, client, principals):
    doc_id = (await _create(client, principals["node1"])).json()["id"]

    resp = await client.put(
        f"/api/documents/{doc_id}", json={"content": "# Beta\n\nv2"}, headers=principals["node1"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Beta"
    assert body["hash"] == hashlib.sha256("# Beta\n\nv2".encode()).hexdigest()


async def test_node_update_cross_node_forbidden(db, client, principals):
    doc_id = (await _create(client, principals["node2"])).json()["id"]

    resp = await client.put(
        f"/api/documents/{doc_id}", json={"content": "x"}, headers=principals["node1"]
    )
    assert resp.status_code == 403
    assert "不属于本节点" in resp.json()["detail"]


async def test_node_update_local_forbidden(db, client, principals):
    doc_id = (await _create(client, principals["admin"])).json()["id"]

    resp = await client.put(
        f"/api/documents/{doc_id}", json={"content": "x"}, headers=principals["node1"]
    )
    assert resp.status_code == 403


async def test_update_missing_document(db, client, principals):
    resp = await client.put(
        "/api/documents/9999", json={"content": "x"}, headers=principals["admin"]
    )
    assert resp.status_code == 404


# ---------- 写入口径单源 ----------


async def test_title_extraction_from_content(db, client, principals):
    resp = await client.post(
        "/api/documents",
        json={"path": "kb/t.md", "title": "", "content": "# From Heading\n\nbody"},
        headers=principals["admin"],
    )
    assert resp.json()["title"] == "From Heading"


async def test_title_fallback_to_path_stem(db, client, principals):
    resp = await client.post(
        "/api/documents",
        json={"path": "kb/no-heading.md", "content": "plain body"},
        headers=principals["admin"],
    )
    assert resp.json()["title"] == "no-heading"


async def test_update_keeps_excluded_sticky(db, client, principals):
    """用户显式移出的文档不因内容变更被拉回."""
    doc_id = (await _create(client, principals["admin"])).json()["id"]
    async with db() as session:
        doc = await session.get(Document, doc_id)
        doc.rag_status = "excluded"
        await session.commit()

    resp = await client.put(
        f"/api/documents/{doc_id}", json={"content": "# New\n\nx"}, headers=principals["admin"]
    )
    assert resp.json()["rag_status"] == "excluded"


async def test_writer_conflict_raises(db):
    from app.services.document_writer import PathConflict, create_document

    async with db() as session:
        await create_document(session, node_id="local", path="a.md", content="# A")
        try:
            await create_document(session, node_id="local", path="a.md", content="# B")
        except PathConflict as e:
            assert e.path == "a.md"
        else:
            raise AssertionError("PathConflict not raised")


async def test_writer_does_not_touch_other_scope(db):
    """写入口径的唯一性判定严格按 (node_id, path),不误判其他归属."""
    from app.services.document_writer import create_document

    async with db() as session:
        await create_document(session, node_id="node-1", path="a.md", content="# A")
        doc = await create_document(session, node_id="node-2", path="a.md", content="# B")
        assert doc.node_id == "node-2"


# ---------- MCP 写工具(Hub 形态) ----------


@pytest_asyncio.fixture
async def mcp_session(db, monkeypatch):
    """把 MCP 处理器的 async_session 指向测试库."""
    from app.services import mcp_server

    monkeypatch.setattr(mcp_server, "async_session", db)
    return db


async def _call(name, arguments):
    from app.services.mcp_server import handle_call_tool

    return await handle_call_tool(
        None, types.CallToolRequestParams(name=name, arguments=arguments)
    )


async def test_mcp_create_document(mcp_session):
    result = await _call("create_document", {"path": "kb/a.md", "content": CONTENT})

    assert not result.is_error
    text = result.content[0].text
    assert "已创建文档" in text
    assert "- 节点: local" in text

    async with mcp_session() as session:
        from sqlalchemy import select

        doc = (await session.execute(select(Document))).scalar_one()
        assert doc.node_id == "local"
        assert doc.hash == hashlib.sha256(CONTENT.encode()).hexdigest()


async def test_mcp_create_conflict_text(mcp_session):
    await _call("create_document", {"path": "kb/a.md", "content": CONTENT})

    result = await _call("create_document", {"path": "kb/a.md", "content": CONTENT})

    assert not result.is_error
    assert "路径已存在" in result.content[0].text
    assert "update_document" in result.content[0].text


async def test_mcp_update_document(mcp_session):
    created = await _call("create_document", {"path": "kb/a.md", "content": CONTENT})
    assert "已创建文档" in created.content[0].text

    async with mcp_session() as session:
        from sqlalchemy import select

        doc_id = (await session.execute(select(Document.id))).scalar_one()

    result = await _call("update_document", {"document_id": doc_id, "content": "# Beta\n\nv2"})

    assert not result.is_error
    assert "已更新文档" in result.content[0].text
    assert "Beta" in result.content[0].text


async def test_mcp_update_missing_text(mcp_session):
    result = await _call("update_document", {"document_id": 9999, "content": "x"})

    assert not result.is_error
    assert "文档 ID 9999 不存在。" == result.content[0].text


async def test_mcp_create_missing_param(mcp_session):
    result = await _call("create_document", {"content": CONTENT})

    assert result.is_error
    assert "缺少参数: path" in result.content[0].text


async def test_mcp_tools_listed():
    from app.services.mcp_server import handle_list_tools

    tools = (await handle_list_tools(None, None)).tools
    assert [t.name for t in tools] == [
        "search_documents",
        "get_document",
        "list_documents",
        "create_document",
        "update_document",
    ]


async def test_rest_and_mcp_write_same_fields(db, client, principals, mcp_session):
    """写入口径单源:REST 与 MCP 写入同一内容,hash / size / title 完全一致."""
    rest = await _create(client, principals["admin"], path="rest.md")
    mcp = await _call("create_document", {"path": "mcp.md", "content": CONTENT})

    assert mcp.content[0].text.startswith("已创建文档")

    async with db() as session:
        from sqlalchemy import select

        docs = {d.path: d for d in (await session.execute(select(Document))).scalars().all()}

    assert docs["rest.md"].hash == docs["mcp.md"].hash
    assert docs["rest.md"].size == docs["mcp.md"].size
    assert docs["rest.md"].title == docs["mcp.md"].title
    assert rest.json()["hash"] == docs["mcp.md"].hash
