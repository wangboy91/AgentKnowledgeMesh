"""端点鉴权矩阵测试(account-auth).

端点组 x 凭证类型(无 / JWT-viewer / JWT-admin / API Token / 节点 token)
断言 401(未认证/凭证无效)、403(角色不足)、200(放行)。
"""

import hashlib

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import ApiToken, Node, User
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
    """准备 admin / viewer / API Token / 节点 四类凭证,返回 {名称: 请求头}."""
    api_token_plain = "akm_matrix_viewer_token"
    async with db() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("pw"), role="admin"),
                User(username="viewer", password_hash=hash_password("pw"), role="viewer"),
                ApiToken(
                    name="matrix",
                    token_hash=hashlib.sha256(api_token_plain.encode()).hexdigest(),
                    token_prefix=api_token_plain[:12],
                    role="viewer",
                ),
                Node(id="node-1", name="n", platform="win", token="b" * 32),
            ]
        )
        await session.commit()

    return {
        "none": {},
        "viewer": {"Authorization": "Bearer " + create_access_token("viewer", "viewer")},
        "admin": {"Authorization": "Bearer " + create_access_token("admin", "admin")},
        "api": {"Authorization": "Bearer " + api_token_plain},
        "node": {"Authorization": "Bearer " + "b" * 32},
    }


# ---------- 读端点:401 无凭证;节点凭证仅放行只读知识端点 ----------


async def test_read_documents(db, client, principals):
    resp = await client.get("/api/documents", headers=principals["none"])
    assert resp.status_code == 401
    for key in ("viewer", "admin", "api", "node"):
        resp = await client.get("/api/documents", headers=principals[key])
        assert resp.status_code == 200, key


async def test_read_search_node_allowed(db, client, principals):
    resp = await client.get("/api/search", params={"q": "x"}, headers=principals["node"])
    assert resp.status_code == 200


async def test_read_rag_stats_node_allowed(db, client, principals):
    resp = await client.get("/api/rag/stats", headers=principals["node"])
    assert resp.status_code == 200


async def test_read_nodes_node_denied(db, client, principals):
    """节点凭证仅限知识端点,不得访问节点管理."""
    resp = await client.get("/api/nodes", headers=principals["node"])
    assert resp.status_code == 403


# ---------- 写端点:401 无凭证 / 403 非管理员 / 200 管理员 ----------


async def test_write_scan_requires_admin(db, client, principals):
    resp = await client.post("/api/documents/scan", headers=principals["none"])
    assert resp.status_code == 401
    resp = await client.post("/api/documents/scan", headers=principals["viewer"])
    assert resp.status_code == 403
    resp = await client.post("/api/documents/scan", headers=principals["api"])
    assert resp.status_code == 403
    resp = await client.post("/api/documents/scan", headers=principals["node"])
    assert resp.status_code == 403
    resp = await client.post("/api/documents/scan", headers=principals["admin"])
    assert resp.status_code == 200


async def test_write_delete_node_requires_admin(db, client, principals):
    resp = await client.delete("/api/nodes/node-1", headers=principals["viewer"])
    assert resp.status_code == 403
    resp = await client.delete("/api/nodes/node-1", headers=principals["node"])
    assert resp.status_code == 403
    resp = await client.delete("/api/nodes/node-1", headers=principals["admin"])
    assert resp.status_code == 200


async def test_auth_admin_only_endpoints(db, client, principals):
    resp = await client.get("/api/auth/users", headers=principals["viewer"])
    assert resp.status_code == 403
    resp = await client.get("/api/auth/users", headers=principals["admin"])
    assert resp.status_code == 200

    resp = await client.get("/api/auth/tokens", headers=principals["viewer"])
    assert resp.status_code == 403
    resp = await client.get("/api/auth/tokens", headers=principals["admin"])
    assert resp.status_code == 200


# ---------- 登录与凭证生命周期 ----------


async def test_login_flow(db, client):
    async with db() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("pw-1"), role="admin"),
                User(username="v", password_hash=hash_password("pw-2"), role="viewer"),
            ]
        )
        await session.commit()

    # 错误密码 401
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401
    # 正确登录
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "pw-1"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    admin_token = resp.json()["access_token"]
    headers = {"Authorization": "Bearer " + admin_token}

    # 修改密码后旧密码失效
    resp = await client.post(
        "/api/auth/change-password",
        json={"old_password": "pw-1", "new_password": "new-pw-9"},
        headers=headers,
    )
    assert resp.status_code == 200
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "pw-1"})
    assert resp.status_code == 401
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "new-pw-9"})
    assert resp.status_code == 200


async def test_api_token_lifecycle(db, client, principals):
    headers = principals["admin"]
    resp = await client.post(
        "/api/auth/tokens", json={"name": "ci", "role": "viewer"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    plaintext = body["token"]
    assert plaintext.startswith("akm_")

    # 明文立即可用;列表不含明文
    resp = await client.get(
        "/api/context", params={"q": "x"}, headers={"Authorization": "Bearer " + plaintext}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/auth/tokens", headers=headers)
    assert all("token" not in item for item in resp.json())

    # 吊销后立即 401
    token_id = body["id"]
    resp = await client.delete("/api/auth/tokens/%d" % token_id, headers=headers)
    assert resp.status_code == 200
    resp = await client.get(
        "/api/context", params={"q": "x"}, headers={"Authorization": "Bearer " + plaintext}
    )
    assert resp.status_code == 401


async def test_api_token_rotate_endpoint(db, client, principals):
    """路由级闭环:轮换后新密钥可用、旧密钥 401,且列表里不产生"已吊销"残留。"""
    headers = principals["admin"]
    resp = await client.post(
        "/api/auth/tokens", json={"name": "ci-rotate", "role": "viewer"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    token_id, old_secret = body["id"], body["token"]

    # 轮换前旧密钥可用
    resp = await client.get(
        "/api/context", params={"q": "x"}, headers={"Authorization": "Bearer " + old_secret}
    )
    assert resp.status_code == 200

    # 轮换:同一条记录换发新密钥
    resp = await client.post("/api/auth/tokens/%d/rotate" % token_id, headers=headers)
    assert resp.status_code == 200
    rotated = resp.json()
    new_secret = rotated["token"]
    assert rotated["id"] == token_id
    assert rotated["name"] == "ci-rotate"
    assert new_secret != old_secret
    assert new_secret.startswith("akm_")

    # 闭环:新密钥可用、旧密钥立即失效
    resp = await client.get(
        "/api/context", params={"q": "x"}, headers={"Authorization": "Bearer " + new_secret}
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/context", params={"q": "x"}, headers={"Authorization": "Bearer " + old_secret}
    )
    assert resp.status_code == 401

    # 列表:仍只有一条记录,且状态是"有效"(不产生"已吊销"残留)
    resp = await client.get("/api/auth/tokens", headers=headers)
    rows = [r for r in resp.json() if r["id"] == token_id]
    assert len(rows) == 1
    assert rows[0]["revoked"] is False

    # 已吊销的 Token 不允许轮换
    resp = await client.delete("/api/auth/tokens/%d" % token_id, headers=headers)
    assert resp.status_code == 200
    resp = await client.post("/api/auth/tokens/%d/rotate" % token_id, headers=headers)
    assert resp.status_code == 400


async def test_api_token_rotate_missing(db, client, principals):
    resp = await client.post("/api/auth/tokens/99999/rotate", headers=principals["admin"])
    assert resp.status_code == 404


async def test_api_token_rotate_requires_admin(db, client, principals):
    resp = await client.post("/api/auth/tokens/1/rotate", headers=principals["viewer"])
    assert resp.status_code == 403


async def test_node_register_rotation(db, client, principals):
    headers = principals["admin"]
    resp = await client.post(
        "/api/nodes/register",
        json={"node_name": "mac", "platform": "darwin"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    node_id, node_token = body["node_id"], body["node_token"]

    payload = {
        "documents": [
            {"path": "a.md", "title": "A", "hash": "h", "size": 1, "content": "# A"}
        ]
    }
    resp = await client.put(
        "/api/nodes/%s/documents" % node_id,
        json=payload,
        headers={"Authorization": "Bearer " + node_token},
    )
    assert resp.status_code == 200

    # 重置后旧 token 失效,新 token 可用
    resp = await client.post("/api/nodes/%s/reset-token" % node_id, headers=headers)
    assert resp.status_code == 200
    new_token = resp.json()["node_token"]
    assert new_token != node_token

    resp = await client.put(
        "/api/nodes/%s/documents" % node_id,
        json=payload,
        headers={"Authorization": "Bearer " + node_token},
    )
    assert resp.status_code == 401
    resp = await client.put(
        "/api/nodes/%s/documents" % node_id,
        json=payload,
        headers={"Authorization": "Bearer " + new_token},
    )
    assert resp.status_code == 200

    # 禁用后上传被拒
    resp = await client.put("/api/nodes/%s" % node_id, json={"disabled": True}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(
        "/api/nodes/%s/documents" % node_id,
        json=payload,
        headers={"Authorization": "Bearer " + new_token},
    )
    assert resp.status_code == 401


async def test_ws_register_token_required(monkeypatch):
    """WS 注册:匿名被拒、有效 token 放行、禁用后拒绝.

    注:WS 会话使用独立内存库并与 lifespan 管理员初始化解耦,
    避免 TestClient 门户线程与外层事件循环共享同一 aiosqlite 连接。
    """
    import app.services.auth as auth_module
    import app.services.websocket as ws_module
    from fastapi.testclient import TestClient

    # 临时文件库 + NullPool:每次取用新建连接,规避 aiosqlite 连接跨事件循环复用的问题
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="akm-ws-test-")
    engine2 = create_async_engine(
        f"sqlite+aiosqlite:///{tmpdir}/ws.db",
        poolclass=NullPool,
    )
    async with engine2.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ws_factory = async_sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)

    async def _noop_ensure_admin():
        return None

    monkeypatch.setattr(auth_module, "ensure_admin_user", _noop_ensure_admin)
    monkeypatch.setattr(ws_module, "async_session", ws_factory)

    node_id, node_token = "ws-node", "c" * 32
    async with ws_factory() as session:
        session.add(Node(id=node_id, name="n", platform="win", token=node_token))
        await session.commit()

    register_msg = {
        "type": "register",
        "node_id": node_id,
        "name": "x",
        "platform": "win",
        "token": node_token,
    }

    with TestClient(app) as tc:
        # 匿名注册被拒
        with tc.websocket_connect("/ws") as conn:
            conn.send_json({"type": "register", "node_id": node_id, "name": "x", "platform": "win"})
            assert conn.receive_json()["type"] == "error"

        # 有效 token 注册成功
        with tc.websocket_connect("/ws") as conn:
            conn.send_json(register_msg)
            assert conn.receive_json()["type"] == "register_ack"

    # 禁用节点后,有效 token 也被拒
    async with ws_factory() as session:
        node = await session.get(Node, node_id)
        node.disabled = True
        await session.commit()

    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as conn:
            conn.send_json(register_msg)
            assert conn.receive_json()["type"] == "error"

    await engine2.dispose()