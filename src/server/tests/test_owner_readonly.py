"""owner 在线读取/源删除/权限的隔离闭环。

运行: cd src/server; uv run --no-sync pytest tests/test_owner_readonly.py -q
临时 SQLite 与两个逻辑 owner，进程内 ASGI/WS 队列，不占端口、不调用模型。
"""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0,str(Path(__file__).parents[2]/'shared'))
from akm_shared.owner_reader import OwnerReader, secure_read
from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import Node, User, ApiToken, Document
from app.models.owner_file import OwnerFile, OwnerVersion
from app.api import owner_files
from app.services.auth import create_access_token
from app.services.owner_gateway import OwnerGateway
from app.services import mcp_server

SENTINEL = 'OWNER_ONLY_SENTINEL_82619'


class LogicalOwnerSocket:
    """经过真实 owner_websocket 注册/消息处理，磁盘操作用真实 OwnerReader。"""
    def __init__(self, reader, token):
        self.reader = reader
        self.input = asyncio.Queue()
        self.output = asyncio.Queue()
        self.input.put_nowait({'type':'owner_register','token':token})
        self.task = None
        self.requests = 0
        self.before_reply = None

    async def accept(self):
        pass

    async def close(self, code=1000):
        await self.output.put({'closed':code})

    async def receive_json(self):
        return await self.input.get()

    async def send_json(self, data):
        if data.get('type')=='owner_request':
            self.requests += 1
            result = await asyncio.to_thread(self.reader.read,data)
            if self.before_reply:
                await self.before_reply()
            await self.input.put({'type':'owner_manifest','files':self.reader.scan()})
            await self.input.put({'type':'owner_response','request_id':data['request_id'],'result':result})
        else:
            await self.output.put(data)

    async def manifest(self):
        await self.input.put({'type':'owner_manifest','files':self.reader.scan()})
        while True:
            item = await asyncio.wait_for(self.output.get(),5)
            if item.get('type')=='manifest_ack':
                return
            if 'closed' in item:
                raise AssertionError('socket closed before manifest ack')


@pytest_asyncio.fixture
async def mesh(tmp_path, monkeypatch):
    database = tmp_path/'hub.sqlite'
    engine = create_async_engine('sqlite+aiosqlite:///'+database.as_posix())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine,expire_on_commit=False)
    async def dependency():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_session] = dependency
    monkeypatch.setattr(owner_files,'async_session',factory)
    monkeypatch.setattr(settings,'owner_readonly_enabled',True)
    monkeypatch.setattr(settings,'owner_memory_clients','node:A,node:B,user:viewer,user:admin,token:1')
    monkeypatch.setattr(settings,'owner_read_timeout',5.0)
    monkeypatch.setattr(settings,'secret_key','isolated-owner-test-key-not-persisted-2026')
    gateway = OwnerGateway()
    monkeypatch.setattr(owner_files,'gateway',gateway)
    async with factory() as session:
        session.add_all([Node(id=n,name=n,platform='windows',token='test-node-'+n) for n in ('A','B','C')])
        session.add_all([User(username=n,role=r,password_hash='unused') for n,r in [('admin','admin'),('viewer','viewer')]])
        session.add(ApiToken(id=1,name='viewer-test',role='viewer',token_prefix='akm_fixture',token_hash=hashlib.sha256(b'akm_fixture').hexdigest()))
        session.add(Document(node_id='A',path='same.md',title='legacy',content=SENTINEL+' legacy',hash='0'*64,size=1))
        await session.commit()
    # 旧库确实仍有全文：严格屏障不得用删数据伪造零副本。
    sockets = {}
    paths = {}
    for name in ('A','B'):
        root = tmp_path/name
        root.mkdir()
        (root/'same.md').write_text(SENTINEL+' '+name,encoding='utf-8')
        paths[name] = root/'same.md'
        reader = OwnerReader([root],tmp_path/(name+'-state.sqlite'))
        socket = LogicalOwnerSocket(reader,'test-node-'+name)
        socket.task = asyncio.create_task(owner_files.owner_websocket(socket))
        assert (await socket.output.get())['type']=='owner_ack'
        await socket.manifest()
        sockets[name] = socket
    headers = {n:{'Authorization':'Bearer test-node-'+n} for n in ('A','B','C')}
    headers.update({n:{'Authorization':'Bearer '+create_access_token(n,r)} for n,r in [('admin','admin'),('viewer','viewer')]})
    headers['token'] = {'Authorization':'Bearer akm_fixture'}
    async with AsyncClient(transport=ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test') as client:
        files = (await client.get('/api/owner-files',headers=headers['A'])).json()
        a = files[0]
        b = (await client.get('/api/owner-files',headers=headers['B'])).json()[0]
        yield SimpleNamespace(client=client,factory=factory,headers=headers,sockets=sockets,paths=paths,a=a,b=b,gateway=gateway,tmp=tmp_path)
    for socket in sockets.values():
        socket.task.cancel()
        try:
            await socket.task
        except asyncio.CancelledError:
            pass
    app.dependency_overrides.pop(get_session,None)
    await engine.dispose()


async def grant(mesh,file,owner,reader,revoked=False):
    response = await mesh.client.put('/api/owner-files/'+file['file_id']+'/grants',headers=mesh.headers[owner],json={
        'subject':reader,'expires_at':int(time.time()+3600),'revoked':revoked})
    assert response.status_code==200,response.text


@pytest.mark.asyncio
async def test_two_owner_live_read_search_no_new_body_persistence(mesh):
    assert mesh.a['file_id']!=mesh.b['file_id']
    assert mesh.a['owner']=='A' and mesh.b['owner']=='B'
    await grant(mesh,mesh.a,'A','node:B')
    await grant(mesh,mesh.b,'B','node:A')
    for owner,peer,file in [('A','B',mesh.a),('B','A',mesh.b)]:
        url='/api/owner-files/'+file['file_id']
        read=await mesh.client.get(url+'/content',headers=mesh.headers[peer])
        assert read.status_code==200,read.text
        assert read.headers['cache-control']=='no-store'
        assert read.json()['content']==mesh.paths[owner].read_text(encoding='utf-8')
        result=await mesh.client.post(url+'/search',headers=mesh.headers[peer],json={'query':SENTINEL})
        assert result.status_code==200 and SENTINEL in result.json()['snippet']
    for name in ('A','B'):
        assert SENTINEL.encode() not in (mesh.tmp/(name+'-state.sqlite')).read_bytes()
    async with mesh.factory() as session:
        from sqlalchemy import inspect
        assert 'content' not in OwnerFile.__table__.columns
        assert 'content' not in OwnerVersion.__table__.columns
        assert (await session.scalar(select(Document.content)))==SENTINEL+' legacy'
        for file in (await session.execute(select(OwnerFile))).scalars():
            assert SENTINEL not in json.dumps(file.to_metadata())


@pytest.mark.asyncio
async def test_permission_failures_and_no_rpc_before_authorization(mesh,monkeypatch):
    url='/api/owner-files/'+mesh.a['file_id']+'/content'
    assert (await mesh.client.get(url)).status_code==401
    for who in ('B','C','admin','viewer','token'):
        assert (await mesh.client.get(url,headers=mesh.headers[who])).status_code==403
    assert mesh.sockets['A'].requests==0
    await grant(mesh,mesh.a,'A','node:B')
    monkeypatch.setattr(settings,'owner_memory_clients','node:A')
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==403
    assert mesh.sockets['A'].requests==0
    response=await mesh.client.put('/api/owner-files/'+mesh.a['file_id']+'/grants',headers=mesh.headers['admin'],json={
        'subject':'node:B','expires_at':int(time.time()+3600)})
    assert response.status_code==403


@pytest.mark.asyncio
async def test_revoked_and_expired_grants(mesh):
    url='/api/owner-files/'+mesh.a['file_id']+'/content'
    await grant(mesh,mesh.a,'A','node:B')
    await grant(mesh,mesh.a,'A','node:B',True)
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==403
    await grant(mesh,mesh.a,'A','node:B')
    from app.models.owner_file import OwnerReadGrant
    async with mesh.factory() as session:
        row=await session.get(OwnerReadGrant,(mesh.a['file_id'],'node:B'))
        row.expires_at=1
        await session.commit()
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==403


@pytest.mark.asyncio
async def test_offline_timeout_disabled_owner_and_unavailable_root(mesh,monkeypatch):
    await grant(mesh,mesh.a,'A','node:B')
    url='/api/owner-files/'+mesh.a['file_id']+'/content'
    connection=mesh.gateway.connections.pop('A')
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==503
    mesh.gateway.connections['A']=connection
    old_send=connection.send_json
    async def no_reply(data):
        pass
    connection.send_json=no_reply
    monkeypatch.setattr(settings,'owner_read_timeout',0.05)
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==503
    assert not mesh.gateway.pending
    connection.send_json=old_send
    async with mesh.factory() as session:
        node=await session.get(Node,'A'); node.disabled=True; await session.commit()
    assert (await mesh.client.get(url,headers=mesh.headers['B'])).status_code==503


@pytest.mark.asyncio
async def test_source_delete_stops_all_owner_and_legacy_read_surfaces(mesh):
    await grant(mesh,mesh.a,'A','node:B')
    file_id=mesh.a['file_id']
    mesh.paths['A'].unlink()
    await mesh.sockets['A'].manifest()
    for suffix in ('','/content','/history'):
        response=await mesh.client.get('/api/owner-files/'+file_id+suffix,headers=mesh.headers['B'])
        assert response.status_code==410 and SENTINEL not in response.text
    response=await mesh.client.post('/api/owner-files/'+file_id+'/search',headers=mesh.headers['B'],json={'query':SENTINEL})
    assert response.status_code==410
    assert (await mesh.client.get('/api/owner-files',headers=mesh.headers['B'])).json()==[mesh.b]
    for path in ('/api/documents','/api/documents/tree','/api/documents/1','/api/search?q='+SENTINEL,
                 '/api/rag/search?q=x','/api/context?q=x','/api/nodes/A/documents','/api/mcp/sse'):
        response=await mesh.client.get(path,headers=mesh.headers['admin'])
        assert response.status_code==409 and SENTINEL not in response.text
    tools=await mcp_server.handle_list_tools(None,None)
    assert tools.tools==[]
    from mcp.types import CallToolRequest
    result=await mcp_server.handle_call_tool(None,SimpleNamespace(name='get_document',arguments={'document_id':1}))
    assert result.is_error and SENTINEL not in str(result)
    async with mesh.factory() as session:
        tombstone=await session.get(OwnerFile,file_id)
        assert tombstone.deleted
        assert await session.scalar(select(Document.content))==SENTINEL+' legacy'


@pytest.mark.asyncio
async def test_old_manifest_cannot_resurrect_and_recreate_needs_new_grant(mesh):
    old={k:v for k,v in mesh.a.items() if k!='owner'}
    mesh.paths['A'].unlink(); await mesh.sockets['A'].manifest()
    old['revision']=100
    await owner_files.accept_manifest('A',{'files':[old]})
    async with mesh.factory() as session:
        assert (await session.get(OwnerFile,mesh.a['file_id'])).deleted
    mesh.paths['A'].write_text(SENTINEL+' recreated',encoding='utf-8')
    await mesh.sockets['A'].manifest()
    fresh=(await mesh.client.get('/api/owner-files',headers=mesh.headers['A'])).json()[0]
    assert fresh['file_id']!=mesh.a['file_id'] and fresh['generation']!=mesh.a['generation']
    assert (await mesh.client.get('/api/owner-files/'+fresh['file_id']+'/content',headers=mesh.headers['B'])).status_code==403


@pytest.mark.asyncio
async def test_delete_while_read_in_flight_is_blocked_before_return(mesh):
    await grant(mesh,mesh.a,'A','node:B')
    async def delete_before_reply():
        mesh.paths['A'].unlink()
    mesh.sockets['A'].before_reply=delete_before_reply
    response=await mesh.client.get('/api/owner-files/'+mesh.a['file_id']+'/content',headers=mesh.headers['B'])
    assert response.status_code==410 and SENTINEL not in response.text


@pytest.mark.asyncio
async def test_write_disabled_is_never_success_and_permissions_preserved(mesh):
    original=mesh.paths['A'].read_bytes()
    url='/api/owner-files/'+mesh.a['file_id']+'/content'
    for who,code in [('viewer',403),('token',403),('B',501),('admin',501)]:
        response=await mesh.client.put(url,headers=mesh.headers[who],json={'content':'must not save'})
        assert response.status_code==code
    assert mesh.paths['A'].read_bytes()==original
    assert mesh.sockets['A'].reader.read({'action':'write'})['status']=='write_not_supported'


def test_reader_identity_local_changes_and_unreachable_root_no_delete(tmp_path):
    root=tmp_path/'root'; root.mkdir(); source=root/'a.md'; source.write_text('one',encoding='utf-8')
    state=tmp_path/'state.sqlite'; reader=OwnerReader([root],state)
    first=reader.scan()[0]
    assert OwnerReader([root],state).scan()[0]['file_id']==first['file_id']
    source.write_text('two',encoding='utf-8')
    second=reader.scan()[0]
    assert second['revision']==first['revision']+1
    assert reader.read({'action':'read',**first})['status']=='conflict'
    root.rename(tmp_path/'unavailable')
    missing=reader.scan()[0]
    assert missing['available'] is False and missing['deleted'] is False


@pytest.mark.parametrize('path',['../outside.md','/outside.md','C:/outside.md','foo:bar.md','a\\b.md','a/../b.md'])
def test_reader_path_rejects(tmp_path,path):
    with pytest.raises(ValueError):
        secure_read(tmp_path,path)


def test_reader_reparse_and_incomplete_scan_no_delete(tmp_path,monkeypatch):
    root=tmp_path/'root'; root.mkdir(); source=root/'a.md'; source.write_text('safe',encoding='utf-8')
    reader=OwnerReader([root],tmp_path/'state.sqlite'); first=reader.scan()[0]
    import akm_shared.owner_reader as module
    original=module.secure_read
    def inaccessible(*args):
        raise PermissionError('test access denied')
    monkeypatch.setattr(module,'secure_read',inaccessible)
    observed=reader.scan()[0]
    assert observed['deleted'] is False and observed['available'] is False
    monkeypatch.setattr(module,'secure_read',original)

@pytest.mark.asyncio
async def test_grant_revoke_while_response_in_flight(mesh):
    await grant(mesh,mesh.a,'A','node:B')
    async def revoke_before_reply():
        await grant(mesh,mesh.a,'A','node:B',True)
    mesh.sockets['A'].before_reply=revoke_before_reply
    response=await mesh.client.get('/api/owner-files/'+mesh.a['file_id']+'/content',headers=mesh.headers['B'])
    assert response.status_code==403 and SENTINEL not in response.text


@pytest.mark.asyncio
async def test_wrong_owner_cannot_complete_other_owners_request():
    gateway=OwnerGateway()
    message=asyncio.Queue()
    class Socket:
        async def send_json(self,value):
            await message.put(value)
    a,b=Socket(),Socket()
    gateway.connect('A',a); gateway.connect('B',b)
    pending=asyncio.create_task(gateway.request('A',{'action':'read'},0.1))
    outgoing=await message.get()
    gateway.reply('B',b,outgoing['request_id'],{'status':'ok','content':'wrong owner'})
    assert not pending.done()
    gateway.reply('A',a,outgoing['request_id'],{'status':'ok','content':'right owner'})
    assert (await pending)['content']=='right owner'


@pytest.mark.asyncio
async def test_manifest_rejects_content_and_owner_impersonation(mesh):
    raw={k:v for k,v in mesh.a.items() if k!='owner'}
    with pytest.raises(ValueError):
        await owner_files.accept_manifest('B',{'files':[raw]})
    raw['content']=SENTINEL
    with pytest.raises(ValueError):
        await owner_files.accept_manifest('A',{'files':[raw]})


@pytest.mark.asyncio
async def test_current_node_token_rotation_closes_owner_session(mesh):
    async with mesh.factory() as session:
        node=await session.get(Node,'A'); node.token='replacement-test-token'; await session.commit()
    await mesh.sockets['A'].input.put({'type':'owner_manifest','files':[]})
    await asyncio.wait_for(mesh.sockets['A'].task,1)
    assert 'A' not in mesh.gateway.connections


@pytest.mark.asyncio
async def test_mode_default_off_does_not_expose_owner_routes(mesh,monkeypatch):
    monkeypatch.setattr(settings,'owner_readonly_enabled',False)
    response=await mesh.client.get('/api/owner-files',headers=mesh.headers['A'])
    assert response.status_code==404


def test_windows_reparse_root_no_tombstone(tmp_path,monkeypatch):
    root=tmp_path/'root'; root.mkdir(); source=root/'a.md'; source.write_text('safe',encoding='utf-8')
    reader=OwnerReader([root],tmp_path/'state.sqlite'); first=reader.scan()[0]
    original=Path.lstat
    def fake_lstat(path,*args,**kwargs):
        info=original(path,*args,**kwargs)
        if path==root:
            return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path,'lstat',fake_lstat)
    observed=reader.scan()[0]
    assert observed['deleted'] is False and observed['available'] is False

@pytest.mark.asyncio
async def test_gateway_send_failure_is_unavailable_not_raw_error():
    gateway=OwnerGateway()
    class FailedSocket:
        async def send_json(self,message):
            raise RuntimeError(SENTINEL)
    gateway.connect('A',FailedSocket())
    with pytest.raises(ConnectionError) as error:
        await gateway.request('A',{'action':'read'},0.1)
    assert SENTINEL not in str(error.value)
    assert not gateway.pending
