"""严格模式 Node 编排隔离测试；不联网、不访问用户目录。

运行: cd src/node; uv run --no-sync pytest tests/test_owner_readonly.py -q
"""
import asyncio
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[2]/'shared'))
from app.config import NodeSettings
from app.owner_readonly import OwnerReadClient
from app import owner_readonly
from app.runner import HubClient


def test_explicit_roots_and_separate_states(tmp_path,monkeypatch):
    monkeypatch.setattr(owner_readonly,'USER_STATE_DIR',tmp_path/'state')
    with pytest.raises(ValueError): OwnerReadClient(NodeSettings(knowledge_roots='',_env_file=None))
    root=tmp_path/'root'; root.mkdir(); (root/'a.md').write_text('owner-only',encoding='utf-8')
    a=OwnerReadClient(NodeSettings(node_id='A',knowledge_roots=str(root),_env_file=None))
    b=OwnerReadClient(NodeSettings(node_id='B',knowledge_roots=str(root),_env_file=None))
    assert a.reader.state_path!=b.reader.state_path
    a.reader.scan(); assert b'owner-only' not in a.reader.state_path.read_bytes()


@pytest.mark.asyncio
async def test_runtime_metadata_read_and_no_write(tmp_path,monkeypatch):
    monkeypatch.setattr(owner_readonly,'USER_STATE_DIR',tmp_path/'state')
    root=tmp_path/'root'; root.mkdir(); (root/'a.md').write_text('owner memory',encoding='utf-8')
    config=NodeSettings(node_id='A',node_token='synthetic-existing-token',knowledge_roots=str(root),owner_readonly_enabled=True,_env_file=None)
    client=OwnerReadClient(config); file=client.reader.scan()[0]
    sent=[]; completed=asyncio.Event(); urls=[]
    class Socket:
        async def send(self,data):
            value=json.loads(data); sent.append(value)
            if value.get('request_id')=='write-test': completed.set()
        async def recv(self): return json.dumps({'node_id':'A','capability':'owner-readonly-v1'})
        def __aiter__(self): return self.messages()
        async def messages(self):
            yield json.dumps({'type':'owner_request','request_id':'read-test','action':'read',**file})
            yield json.dumps({'type':'owner_request','request_id':'write-test','action':'write',**file})
            await asyncio.Event().wait()
    class Connection:
        async def __aenter__(self): return Socket()
        async def __aexit__(self,*args): pass
    def connect(url,**kwargs): urls.append(url); return Connection()
    monkeypatch.setattr(owner_readonly.websockets,'connect',connect)
    task=asyncio.create_task(client.run()); await asyncio.wait_for(completed.wait(),2); task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert urls==['ws://localhost:8000/owner-ws']
    assert all('content' not in str(m) for m in sent if m['type']=='owner_manifest')
    replies={m['request_id']:m['result'] for m in sent if m['type']=='owner_response'}
    assert replies['read-test']['content']=='owner memory'
    assert replies['write-test']['status']=='write_not_supported'
    assert (root/'a.md').read_text(encoding='utf-8')=='owner memory'


@pytest.mark.asyncio
async def test_strict_runner_skips_legacy(tmp_path,monkeypatch):
    seen=[]
    class Reader:
        def __init__(self,settings): seen.append(settings)
        async def run(self): seen.append('ran')
    monkeypatch.setattr(owner_readonly,'OwnerReadClient',Reader)
    root=tmp_path/'root'; root.mkdir()
    config=NodeSettings(node_id='A',knowledge_roots=str(root),owner_readonly_enabled=True,_env_file=None)
    client=HubClient(config)
    async def forbidden(): raise AssertionError('legacy fulltext sync started')
    monkeypatch.setattr(client.transport,'connect',forbidden)
    monkeypatch.setattr(client.sync,'sync_documents',forbidden)
    await client.run(); assert seen==[config,'ran']
