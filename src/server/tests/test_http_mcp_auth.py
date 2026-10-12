"""HTTP MCP 权限、会话归属及三个查询的隔离回归。

运行: cd src/server; uv run --no-sync pytest tests/test_http_mcp_auth.py -q
内存 SQLite + 进程内 ASGI，不扫描磁盘、不调用模型、不占端口。
结果显式保留在 .workbuddy-ai/verification/query-trace-2026-10-12.json。
"""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import User, ApiToken, Document
from app.services import mcp_server
from app.services.auth import create_access_token


@pytest_asyncio.fixture
async def isolated(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite://', poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async def dependency():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_session] = dependency
    monkeypatch.setattr(mcp_server, 'async_session', factory)
    from app.config import settings
    monkeypatch.setattr(settings, 'secret_key', 'isolated-test-key-no-persistence-2026')
    async with factory() as session:
        session.add_all([User(username=name, role=role, password_hash='unused')
                         for name, role in [('admin', 'admin'), ('viewer', 'viewer'), ('other', 'admin')]])
        for value in ('akm_test_one', 'akm_test_two'):
            session.add(ApiToken(name=value, role='viewer', token_prefix=value,
                                 token_hash=hashlib.sha256(value.encode()).hexdigest()))
        for index, (title, content) in enumerate([
            ('跨电脑同步', 'Hub 汇聚两个 Node 上传的 Markdown。'),
            ('工作交接', '记录目标、已完成工作、验证证据和唯一下一步。'),
            ('检索增强生成', 'RAG 先检索相关片段，再用片段支持回答。'),
        ]):
            session.add(Document(node_id='local', path=f'test/{index}.md', title=title,
                                 content=content, hash=hashlib.sha256(content.encode()).hexdigest(),
                                 size=len(content.encode()), rag_status='not_indexed'))
        await session.commit()
    headers = {name: {'Authorization': 'Bearer ' + create_access_token(name, role)}
               for name, role in [('admin', 'admin'), ('viewer', 'viewer'), ('other', 'admin')]}
    headers.update({value: {'Authorization': 'Bearer ' + value}
                    for value in ('akm_test_one', 'akm_test_two')})
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as client:
        yield factory, client, headers
    app.dependency_overrides.pop(get_session, None)
    await engine.dispose()


@asynccontextmanager
async def sse(headers):
    frames = asyncio.Queue()
    disconnect = asyncio.Event()
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': 'GET', 'scheme': 'http', 'path': '/api/mcp/sse',
             'raw_path': b'/api/mcp/sse', 'query_string': b'', 'root_path': '',
             'headers': [(b'host', b'test'), (b'accept', b'text/event-stream')] +
                        [(key.lower().encode(), value.encode()) for key, value in headers.items()],
             'client': ('127.0.0.1', 12345), 'server': ('test', 80)}
    async def receive():
        await disconnect.wait()
        return {'type': 'http.disconnect'}
    async def send(message):
        if message['type'] == 'http.response.body' and message.get('body'):
            await frames.put(message['body'].decode())
    task = asyncio.create_task(app(scope, receive, send))
    try:
        frame = await asyncio.wait_for(frames.get(), 5)
        endpoint = next(line[6:] for line in frame.splitlines() if line.startswith('data: '))
        yield endpoint, frames
    finally:
        disconnect.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def rpc(client, headers, endpoint, frames, method, params, number=1):
    response = await client.post(endpoint, headers=headers, json={
        'jsonrpc': '2.0', 'id': number, 'method': method, 'params': params})
    assert response.status_code == 202
    while True:
        frame = await asyncio.wait_for(frames.get(), 5)
        for line in frame.splitlines():
            if line.startswith('data: '):
                value = json.loads(line[6:])
                if value.get('id') == number:
                    return value


async def initialize(client, headers, endpoint, frames):
    await rpc(client, headers, endpoint, frames, 'initialize', {
        'protocolVersion': '2024-11-05', 'capabilities': {},
        'clientInfo': {'name': 'isolated-test', 'version': '1'}})
    response = await client.post(endpoint, headers=headers, json={
        'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    assert response.status_code == 202


async def test_three_query_trace(isolated):
    factory, client, headers = isolated
    rows = []
    for question, query in [('跨电脑资料如何同步？', '跨电脑同步'),
                            ('工作交接应记录什么？', '工作交接'),
                            ('RAG 是什么流程？', '检索增强生成')]:
        response = await client.get('/api/search', headers=headers['viewer'], params={'q': query})
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 1
        doc_id = body['documents'][0]['id']
        detail = await client.get(f'/api/documents/{doc_id}', headers=headers['viewer'])
        assert detail.status_code == 200
        result = await mcp_server._search_documents(query, 5)
        assert query in result.content[0].text
        rows.append({'question': question, 'query': query, 'mode': 'keyword',
                     'http_status': response.status_code, 'result': body,
                     'detail': detail.json(), 'mcp_text': result.content[0].text})
    natural = await client.get('/api/search', headers=headers['viewer'],
                               params={'q': '工作交接应记录什么？'})
    assert natural.json()['count'] == 0
    output = Path(__file__).resolve().parents[3] / '.workbuddy-ai/verification/query-trace-2026-10-12.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'path': 'ASGI /api/search → SQL LIKE → Document → /api/documents/{id}',
                                  'queries': rows, 'natural_question': natural.json(),
                                  'boundary': '关键词验证，不代表语义 RAG 或答案生成质量'}, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('credential', ['viewer', 'akm_test_one'])
@pytest.mark.parametrize('tool', ['create_document', 'update_document'])
async def test_viewer_write_denied(isolated, credential, tool):
    factory, client, headers = isolated
    arguments = {'path': 'test/new.md', 'content': '# unauthorized'} if tool == 'create_document' else {'document_id': 1, 'content': '# unauthorized'}
    async with sse(headers[credential]) as (endpoint, frames):
        await initialize(client, headers[credential], endpoint, frames)
        value = await rpc(client, headers[credential], endpoint, frames, 'tools/call',
                          {'name': tool, 'arguments': arguments}, 2)
        assert value['result'].get('isError') is True
    async with factory() as session:
        docs = (await session.execute(select(Document))).scalars().all()
        assert len(docs) == 3
        assert all('unauthorized' not in doc.content for doc in docs)


@pytest.mark.parametrize('owner,other', [('admin', 'viewer'), ('admin', 'other'),
                                       ('akm_test_one', 'akm_test_two')])
async def test_session_owner_and_cleanup(isolated, owner, other):
    _, client, headers = isolated
    async with sse(headers[owner]) as (endpoint, frames):
        await initialize(client, headers[owner], endpoint, frames)
        response = await client.post(endpoint, headers=headers[other], json={
            'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'})
        assert response.status_code == 404
    response = await client.post(endpoint, headers=headers[owner], json={
        'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'})
    assert response.status_code == 404


async def test_admin_write_and_role_downgrade(isolated):
    factory, client, headers = isolated
    async with sse(headers['admin']) as (endpoint, frames):
        await initialize(client, headers['admin'], endpoint, frames)
        value = await rpc(client, headers['admin'], endpoint, frames, 'tools/call',
                          {'name': 'create_document', 'arguments': {'path': 'test/admin.md', 'content': '# permitted'}}, 2)
        assert not value['result'].get('isError', False)
        renewed = {'Authorization': 'Bearer ' + create_access_token('admin', 'admin')}
        response = await client.post(endpoint, headers=renewed, json={
            'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list'})
        assert response.status_code == 404
        async with factory() as session:
            user = (await session.execute(select(User).where(User.username == 'admin'))).scalar_one()
            user.role = 'viewer'
            await session.commit()
        value = await rpc(client, headers['admin'], endpoint, frames, 'tools/call',
                          {'name': 'update_document', 'arguments': {'document_id': 1, 'content': '# unauthorized'}}, 3)
        assert value['result'].get('isError') is True
    async with factory() as session:
        docs = (await session.execute(select(Document))).scalars().all()
        assert len(docs) == 4
        assert all(doc.node_id == 'local' for doc in docs)
        assert all('unauthorized' not in doc.content for doc in docs)


async def test_viewer_http_read_and_revocation(isolated):
    factory, client, headers = isolated
    async with sse(headers['akm_test_one']) as (endpoint, frames):
        await initialize(client, headers['akm_test_one'], endpoint, frames)
        value = await rpc(client, headers['akm_test_one'], endpoint, frames, 'tools/call',
                          {'name': 'search_documents', 'arguments': {'query': '工作交接'}}, 2)
        assert not value['result'].get('isError', False)
        assert '工作交接' in value['result']['content'][0]['text']
        from datetime import datetime
        async with factory() as session:
            token = (await session.execute(select(ApiToken).where(ApiToken.name == 'akm_test_one'))).scalar_one()
            token.revoked_at = datetime.now()
            await session.commit()
        response = await client.post(endpoint, headers=headers['akm_test_one'], json={
            'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'})
        assert response.status_code == 401


async def test_http_missing_principal_fails_closed(isolated):
    from starlette.requests import Request
    import mcp.types as types
    result = await mcp_server.handle_call_tool(
        SimpleNamespace(request=Request({'type': 'http'})),
        types.CallToolRequestParams(name='create_document', arguments={'path': 'missing.md', 'content': '# blocked'}),
    )
    assert result.is_error
    assert '401' in result.content[0].text


async def test_anonymous_and_disabled_user_denied(isolated):
    factory, client, headers = isolated
    async with sse(headers['admin']) as (endpoint, frames):
        await initialize(client, headers['admin'], endpoint, frames)
        payload = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': 'create_document', 'arguments': {'path': 'blocked.md', 'content': '# unauthorized'}}}
        response = await client.post(endpoint, json=payload)
        assert response.status_code == 401
        response = await client.get('/api/mcp/sse')
        assert response.status_code == 401
        async with factory() as session:
            user = (await session.execute(select(User).where(User.username == 'admin'))).scalar_one()
            user.disabled = True
            await session.commit()
        response = await client.post(endpoint, headers=headers['admin'], json=payload)
        assert response.status_code == 401
        response = await client.get('/api/mcp/sse', headers=headers['admin'])
        assert response.status_code == 401
    async with factory() as session:
        assert len((await session.execute(select(Document))).scalars().all()) == 3


async def test_concurrent_sessions_keep_separate_principals(isolated):
    factory, client, headers = isolated
    async with sse(headers['admin']) as (admin_endpoint, admin_frames):
        async with sse(headers['viewer']) as (viewer_endpoint, viewer_frames):
            await asyncio.gather(
                initialize(client, headers['admin'], admin_endpoint, admin_frames),
                initialize(client, headers['viewer'], viewer_endpoint, viewer_frames),
            )
            admin_result, viewer_result = await asyncio.gather(
                rpc(client, headers['admin'], admin_endpoint, admin_frames, 'tools/call', {
                    'name': 'create_document', 'arguments': {'path': 'concurrent/admin.md', 'content': '# permitted'}}, 2),
                rpc(client, headers['viewer'], viewer_endpoint, viewer_frames, 'tools/call', {
                    'name': 'update_document', 'arguments': {'document_id': 1, 'content': '# unauthorized'}}, 2),
            )
            assert not admin_result['result'].get('isError', False)
            assert viewer_result['result'].get('isError') is True
    async with factory() as session:
        docs = (await session.execute(select(Document))).scalars().all()
        assert len(docs) == 4
        assert all('unauthorized' not in doc.content for doc in docs)


async def test_stdio_local_trust_explicit(isolated):
    import mcp.types as types
    factory, _, _ = isolated
    result = await mcp_server.handle_call_tool(
        SimpleNamespace(request=None),
        types.CallToolRequestParams(name='create_document', arguments={
            'path': 'stdio/trusted.md', 'content': '# local trust'}),
    )
    assert not result.is_error
    async with factory() as session:
        doc = (await session.execute(select(Document).where(Document.path == 'stdio/trusted.md'))).scalar_one()
        assert doc.node_id == 'local'
