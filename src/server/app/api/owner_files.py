"""默认关闭的严格 owner 只读 API；元数据持久化，正文只在内存返回。

旧全文接口由严格模式入口屏障隔离；写回暂不支持，不接受正文写入。
"""
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.config import settings
from app.db import async_session, get_session
from app.models.node import Node
from app.models.owner_file import OwnerFile, OwnerReadGrant, OwnerVersion
from app.services.auth import require_auth, resolve_principal
from app.services.owner_gateway import gateway

router = APIRouter()


def enabled():
    if not settings.owner_readonly_enabled:
        raise HTTPException(404, 'Owner mode disabled')


def subject(principal):
    if principal.kind == 'node':
        return 'node:' + principal.node_id
    if principal.kind == 'api_token':
        return 'token:' + str(principal.api_token_id)
    return 'user:' + principal.username


async def allowed(session, file, principal):
    if file.deleted:
        raise HTTPException(410, 'Source deleted')
    node = await session.get(Node, file.owner)
    if node is None or node.disabled:
        raise HTTPException(503, 'Owner unavailable')
    if principal.kind == 'node' and principal.node_id == file.owner:
        return
    grant = await session.get(OwnerReadGrant, (file.file_id, subject(principal)))
    if not grant or grant.revoked or grant.generation != file.generation or grant.expires_at <= time.time():
        raise HTTPException(403, 'Owner read permission required')


async def get_file(session, file_id):
    file = await session.get(OwnerFile, file_id)
    if file is None:
        raise HTTPException(404, 'Owner file not found')
    return file


class Metadata(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    file_id: str
    root_id: str
    path: str = Field(min_length=1, max_length=1024)
    generation: str
    revision: int = Field(ge=1, le=2**31-1)
    hash: str = Field(pattern='^[0-9a-f]{64}$')
    size: int = Field(ge=0, le=1024*1024)
    deleted: bool
    available: bool

    def checked(self):
        for value in (self.file_id,self.root_id,self.generation):
            if str(UUID(value)) != value:
                raise ValueError('invalid ID')
        if ':' in self.path or '\\' in self.path or any(p in ('','.','..') for p in self.path.split('/')):
            raise ValueError('invalid path')
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    files: list[Metadata] = Field(max_length=5000)


async def accept_manifest(owner, raw):
    # 不把 ValidationError/input 或原始载荷写日志/返回错误。
    manifest = Manifest.model_validate(raw)
    files = [m.checked() for m in manifest.files]
    if len({m.file_id for m in files}) != len(files):
        raise ValueError('duplicate ID')
    async with async_session() as session:
        for meta in files:
            file = await session.get(OwnerFile, meta.file_id)
            if file and (file.owner != owner or file.generation != meta.generation or file.path != meta.path or file.root_id != meta.root_id):
                raise ValueError('identity mismatch')
            if file and (file.deleted or meta.revision < file.revision):
                continue  # tombstone 不复活，旧序列不回退。
            if file and meta.revision == file.revision:
                if file.hash != meta.hash or file.deleted != meta.deleted:
                    raise ValueError('revision mismatch')
                file.available = meta.available
                continue
            if file is None:
                active = await session.scalar(select(OwnerFile.file_id).where(OwnerFile.owner==owner, OwnerFile.root_id==meta.root_id, OwnerFile.path==meta.path, OwnerFile.deleted.is_(False)))
                if active is not None and not meta.deleted:
                    raise ValueError('active path already bound')
                file = OwnerFile(owner=owner, **meta.model_dump())
                session.add(file)
            else:
                file.revision, file.hash, file.size = meta.revision, meta.hash, meta.size
                file.deleted, file.available = meta.deleted, meta.available
            session.add(OwnerVersion(file_id=file.file_id,revision=file.revision,hash=file.hash,deleted=file.deleted))
        await session.commit()


async def owner_websocket(websocket: WebSocket):
    if not settings.owner_readonly_enabled:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    owner = None
    try:
        import asyncio
        register = await asyncio.wait_for(websocket.receive_json(),5)
        if set(register) != {'type','token'} or register['type'] != 'owner_register':
            raise ValueError('registration')
        token = register['token']
        async with async_session() as session:
            principal = await resolve_principal(token, session)
        if principal is None or principal.kind != 'node':
            raise ValueError('authentication')
        owner = principal.node_id
        gateway.connect(owner, websocket)
        await websocket.send_json({'type':'owner_ack','node_id':owner,'capability':'owner-readonly-v1'})
        while True:
            message = await websocket.receive_json()
            # 每条消息重新校验当前 token，禁用/轮换即时失效，不信任自报 node_id。
            async with async_session() as session:
                current = await resolve_principal(token, session)
            if current is None or current.kind != 'node' or current.node_id != owner:
                raise ValueError('revoked')
            if message.get('type') == 'owner_manifest' and set(message) == {'type','files'}:
                await accept_manifest(owner, {'files':message['files']})
                await websocket.send_json({'type':'manifest_ack'})
            elif message.get('type') == 'owner_response' and set(message) == {'type','request_id','result'}:
                gateway.reply(owner, websocket, message['request_id'], message['result'])
            else:
                raise ValueError('unsupported message')
    except (WebSocketDisconnect, ValueError, TypeError, KeyError, TimeoutError):
        pass
    except Exception:
        # SQL/协议异常同样禁止打印载荷；断开，让请求如实失败。
        pass
    finally:
        if owner:
            gateway.disconnect(owner, websocket)
        try:
            await websocket.close(code=1008)
        except RuntimeError:
            pass


@router.get('')
async def list_files(q: str = '', principal=Depends(require_auth('viewer',allow_node=True)),session=Depends(get_session)):
    enabled()
    files = (await session.execute(select(OwnerFile).where(OwnerFile.deleted.is_(False)))).scalars().all()
    visible = []
    for file in files:
        try:
            await allowed(session,file,principal)
        except HTTPException:
            continue
        if q.casefold() in file.path.casefold():
            visible.append(file.to_metadata())
    return visible


class ReadGrant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: str = Field(pattern='^(node|user|token):[^:]{1,200}$')
    expires_at: int
    revoked: bool = False


@router.put('/{file_id}/grants')
async def grant_read(file_id: str, body: ReadGrant, principal=Depends(require_auth('viewer',allow_node=True)), session=Depends(get_session)):
    enabled()
    file = await get_file(session,file_id)
    if principal.kind != 'node' or principal.node_id != file.owner or file.deleted:
        raise HTTPException(403,'Only owner may grant access')
    if not time.time() < body.expires_at <= time.time()+30*86400:
        raise HTTPException(400,'Invalid expiry')
    grant = await session.get(OwnerReadGrant,(file_id,body.subject))
    if grant is None:
        grant = OwnerReadGrant(file_id=file_id,subject=body.subject,generation=file.generation)
        session.add(grant)
    grant.expires_at,grant.revoked = body.expires_at,body.revoked
    await session.commit()
    return {'status':'revoked' if body.revoked else 'granted','generation':file.generation}


@router.get('/{file_id}')
async def metadata(file_id: str, principal=Depends(require_auth('viewer',allow_node=True)),session=Depends(get_session)):
    enabled()
    file = await get_file(session,file_id)
    await allowed(session,file,principal)
    return file.to_metadata()


@router.get('/{file_id}/history')
async def history(file_id: str,principal=Depends(require_auth('viewer',allow_node=True)),session=Depends(get_session)):
    enabled()
    file = await get_file(session,file_id)
    await allowed(session,file,principal)
    rows = (await session.execute(select(OwnerVersion).where(OwnerVersion.file_id==file_id).order_by(OwnerVersion.revision))).scalars().all()
    return [{'revision':r.revision,'hash':r.hash,'deleted':r.deleted} for r in rows]


async def body_request(file_id, action, principal, session, authorization, query=''):
    enabled()
    if subject(principal) not in {s.strip() for s in settings.owner_memory_clients.split(',') if s.strip()}:
        raise HTTPException(403,'Memory-only client not verified')
    file = await get_file(session,file_id)
    await allowed(session,file,principal)
    if not file.available:
        raise HTTPException(503,'Owner root unavailable')
    expected = file.to_metadata()
    try:
        result = await gateway.request(file.owner,{'action':action,'file_id':file.file_id,'generation':file.generation,
            'revision':file.revision,'hash':file.hash,'query':query},settings.owner_read_timeout)
    except (ConnectionError,TimeoutError):
        raise HTTPException(503,'Owner offline or timed out') from None
    # 返回前使用新 session 重读墓碑、版本、授权和调用者身份；不复用 ORM 缓存。
    async with async_session() as fresh:
        current = await resolve_principal(authorization[7:].strip(),fresh)
        if current is None or subject(current) != subject(principal):
            raise HTTPException(401,'Credentials no longer valid')
        latest = await get_file(fresh,file_id)
        await allowed(fresh,latest,current)
        if not latest.available:
            raise HTTPException(503,'Owner root unavailable')
        if latest.revision != expected['revision'] or latest.hash != expected['hash']:
            raise HTTPException(409,'Owner version changed; retry metadata')
    if not isinstance(result,dict) or result.get('status') != 'ok':
        status = result.get('status') if isinstance(result,dict) else None
        raise HTTPException(409 if status=='conflict' else 503,'Owner did not provide current content')
    returned = result.get('file',{})
    if not isinstance(returned,dict):
        raise HTTPException(503,'Invalid owner metadata response')
    if any(returned.get(k)!=expected[k] for k in ('file_id','generation','revision','hash')):
        raise HTTPException(409,'Owner version mismatch')
    value = result.get('content' if action=='read' else 'snippet')
    if value is not None and (not isinstance(value,str) or len(value.encode('utf-8'))>1024*1024):
        raise HTTPException(503,'Invalid owner response')
    if action=='read':
        import hashlib
        if value is None or hashlib.sha256(value.encode('utf-8')).hexdigest()!=expected['hash']:
            raise HTTPException(409,'Owner content hash mismatch')
    from fastapi.responses import JSONResponse
    return JSONResponse({'file':expected,'content' if action=='read' else 'snippet':value},headers={'Cache-Control':'no-store','Pragma':'no-cache'})


@router.get('/{file_id}/content')
async def read_content(file_id: str, principal=Depends(require_auth('viewer',allow_node=True)),session=Depends(get_session),authorization: str=Header(...)):
    return await body_request(file_id,'read',principal,session,authorization)


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1,max_length=256)


@router.post('/{file_id}/search')
async def search_content(file_id: str,body: SearchQuery,principal=Depends(require_auth('viewer',allow_node=True)),session=Depends(get_session),authorization: str=Header(...)):
    return await body_request(file_id,'search',principal,session,authorization,body.query)


@router.put('/{file_id}/content')
async def write_disabled(file_id: str,principal=Depends(require_auth('admin',node_write=True))):
    enabled()
    raise HTTPException(501,'Owner write-back is not supported; no content saved')
