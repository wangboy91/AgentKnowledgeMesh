"""认证核心单元测试(account-auth).

覆盖口令哈希、JWT 签发/校验、三类凭证解析(JWT / API Token / 节点 token)。
"""

import jwt as pyjwt
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import ApiToken, Node, User
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    resolve_principal,
    verify_password,
)


@pytest_asyncio.fixture
async def db():
    """独立的内存数据库."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


# ---------- 口令哈希 ----------


def test_password_hash_roundtrip():
    h = hash_password("s3cret-密码")
    assert h.startswith("$akm-pbkdf2$")
    assert verify_password("s3cret-密码", h)
    assert not verify_password("wrong", h)


def test_password_hash_unique_salt():
    assert hash_password("same") != hash_password("same")


def test_verify_password_malformed_hash():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "$akm-pbkdf2$abc$salt$deadbeef")


# ---------- JWT ----------


def test_jwt_roundtrip():
    token = create_access_token("alice", "admin")
    claims = decode_access_token(token)
    assert claims["sub"] == "alice"
    assert claims["role"] == "admin"


def test_jwt_invalid_token():
    assert decode_access_token("garbage.token.value") is None


def test_jwt_expired():
    from datetime import datetime, timedelta, timezone

    from app.services.auth import _secret_key

    payload = {
        "sub": "alice",
        "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired = pyjwt.encode(payload, _secret_key(), algorithm="HS256")
    assert decode_access_token(expired) is None


# ---------- 凭证解析 ----------


@pytest.mark.asyncio
async def test_resolve_principal_user(db):
    async with db() as session:
        session.add(User(username="alice", password_hash=hash_password("pw"), role="admin"))
        await session.commit()

    async with db() as session:
        principal = await resolve_principal(create_access_token("alice", "admin"), session)
        assert principal is not None
        assert principal.kind == "user"
        assert principal.role == "admin"


@pytest.mark.asyncio
async def test_resolve_principal_user_disabled(db):
    async with db() as session:
        session.add(
            User(username="bob", password_hash=hash_password("pw"), role="viewer", disabled=True)
        )
        await session.commit()

    async with db() as session:
        assert await resolve_principal(create_access_token("bob", "viewer"), session) is None


@pytest.mark.asyncio
async def test_resolve_principal_api_token(db):
    async with db() as session:
        session.add(
            ApiToken(
                name="ci",
                token_hash=__import__("hashlib").sha256(b"akm_testtoken").hexdigest(),
                token_prefix="akm_testt",
                role="viewer",
            )
        )
        await session.commit()

    async with db() as session:
        principal = await resolve_principal("akm_testtoken", session)
        assert principal is not None
        assert principal.kind == "api_token"
        assert principal.role == "viewer"


@pytest.mark.asyncio
async def test_resolve_principal_api_token_revoked(db):
    from datetime import datetime

    async with db() as session:
        session.add(
            ApiToken(
                name="revoked",
                token_hash=__import__("hashlib").sha256(b"akm_old").hexdigest(),
                token_prefix="akm_old",
                role="viewer",
                revoked_at=datetime(2020, 1, 1),
            )
        )
        await session.commit()

    async with db() as session:
        assert await resolve_principal("akm_old", session) is None


@pytest.mark.asyncio
async def test_resolve_principal_node(db):
    async with db() as session:
        session.add(Node(id="node-1", name="n", platform="win", token="a" * 32))
        await session.commit()

    async with db() as session:
        principal = await resolve_principal("a" * 32, session)
        assert principal is not None
        assert principal.kind == "node"
        assert principal.node_id == "node-1"


@pytest.mark.asyncio
async def test_resolve_principal_unknown(db):
    async with db() as session:
        assert await resolve_principal("no-such-credential", session) is None


# ---------- API Token 吊销 / 彻底删除 ----------


@pytest.mark.asyncio
async def test_revoke_token_marks_revoked(db):
    from app.services.api_tokens import list_tokens, revoke_token

    async with db() as session:
        session.add(
            ApiToken(name="live", token_hash="h1", token_prefix="akm_live", role="viewer")
        )
        await session.commit()
        token_id = (await list_tokens(session))[0]["id"]

    async with db() as session:
        assert await revoke_token(session, token_id) is True

    async with db() as session:
        row = (await list_tokens(session))[0]
        # 吊销是软删除:记录仍在,状态标记为 revoked
        assert row["revoked"] is True
        # 再次吊销返回 False(幂等)
        assert await revoke_token(session, token_id) is False


@pytest.mark.asyncio
async def test_purge_token_removes_row(db):
    from datetime import datetime

    from app.services.api_tokens import list_tokens, purge_token

    async with db() as session:
        session.add(
            ApiToken(
                name="dead",
                token_hash="h2",
                token_prefix="akm_dead",
                role="viewer",
                revoked_at=datetime(2020, 1, 1),
            )
        )
        await session.commit()
        token_id = (await list_tokens(session))[0]["id"]

    async with db() as session:
        assert await purge_token(session, token_id) is True

    async with db() as session:
        assert await list_tokens(session) == []


@pytest.mark.asyncio
async def test_purge_token_rejects_active(db):
    from app.services.api_tokens import list_tokens, purge_token

    async with db() as session:
        session.add(
            ApiToken(name="live", token_hash="h3", token_prefix="akm_live", role="viewer")
        )
        await session.commit()
        token_id = (await list_tokens(session))[0]["id"]

    async with db() as session:
        # 活跃 Token 必须先吊销,不允许直接硬删除
        with pytest.raises(ValueError):
            await purge_token(session, token_id)

    async with db() as session:
        assert len(await list_tokens(session)) == 1


@pytest.mark.asyncio
async def test_purge_token_missing(db):
    from app.services.api_tokens import purge_token

    async with db() as session:
        assert await purge_token(session, 99999) is False


# ---------- API Token 轮换(闭环) ----------


@pytest.mark.asyncio
async def test_rotate_token_replaces_secret(db):
    """轮换闭环:同一记录换密钥,新密钥可用、旧密钥立即失效,且不产生"已吊销"残留。"""
    from app.services.api_tokens import create_token, list_tokens, rotate_token
    from app.services.auth import resolve_principal

    async with db() as session:
        token, old_plaintext = await create_token(session, "ci-agent", "admin")
        token_id = token.id

    async with db() as session:
        result = await rotate_token(session, token_id)
        assert result is not None
        rotated, new_plaintext = result
        assert rotated.id == token_id  # 记录不变
        assert rotated.name == "ci-agent"  # 名称 / 角色保留
        assert rotated.role == "admin"
        assert rotated.revoked_at is None  # 仍然是有效 Token
        assert new_plaintext != old_plaintext

    async with db() as session:
        rows = await list_tokens(session)
        assert len(rows) == 1  # 没有多出一条"已吊销"记录
        assert rows[0]["id"] == token_id
        assert rows[0]["revoked"] is False
        # 闭环:新密钥可认证
        assert await resolve_principal(new_plaintext, session) is not None
        # 闭环:旧密钥立即失效
        assert await resolve_principal(old_plaintext, session) is None


@pytest.mark.asyncio
async def test_rotate_token_rejects_revoked(db):
    from app.services.api_tokens import create_token, list_tokens, revoke_token, rotate_token

    async with db() as session:
        token, _ = await create_token(session, "dead", "viewer")
        token_id = token.id

    async with db() as session:
        assert await revoke_token(session, token_id) is True

    async with db() as session:
        # 已吊销的凭证不允许靠"轮换"隐式复活
        with pytest.raises(ValueError):
            await rotate_token(session, token_id)

    async with db() as session:
        assert (await list_tokens(session))[0]["revoked"] is True


@pytest.mark.asyncio
async def test_rotate_token_missing(db):
    from app.services.api_tokens import rotate_token

    async with db() as session:
        assert await rotate_token(session, 99999) is None
