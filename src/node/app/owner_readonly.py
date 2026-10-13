"""严格模式 Node：只上报元数据，按需在内存回复正文；不运行旧全文同步。"""
import asyncio
import json
import hashlib
from pathlib import Path

import websockets
from akm_shared.owner_reader import OwnerReader
from app.config import USER_STATE_DIR


class OwnerReadClient:
    def __init__(self, settings):
        if not settings.knowledge_roots.strip():
            raise ValueError('Owner mode requires explicit knowledge roots')
        roots = [Path(r.strip()).expanduser() for r in settings.knowledge_roots.split(',') if r.strip()]
        namespace = hashlib.sha256((settings.hub_url+'|'+settings.get_node_id()).encode()).hexdigest()[:24]
        self.reader = OwnerReader(roots, USER_STATE_DIR / 'owner-readonly' / (namespace+'.sqlite'))
        self.settings = settings

    async def run(self):
        while True:
            try:
                url = self.settings.hub_url.rstrip('/')
                if not url.endswith('/ws'):
                    raise ValueError('Hub URL must end in /ws')
                url = url[:-3] + '/owner-ws'
                async with websockets.connect(url, max_size=2*1024*1024) as ws:
                    await ws.send(json.dumps({'type':'owner_register','token':self.settings.node_token}))
                    ack = json.loads(await ws.recv())
                    if ack.get('capability')!='owner-readonly-v1' or ack.get('node_id')!=self.settings.get_node_id():
                        raise ValueError('Owner capability not accepted')
                    send_lock = asyncio.Lock()
                    reader_lock = asyncio.Lock()
                    async def send(value):
                        async with send_lock:
                            await ws.send(json.dumps(value))
                    async def scan():
                        async with reader_lock:
                            files = await asyncio.to_thread(self.reader.scan)
                        await send({'type':'owner_manifest','files':files})
                    async def reconcile():
                        while True:
                            await asyncio.sleep(max(1,self.settings.owner_scan_seconds))
                            await scan()
                    await scan()
                    ticker = asyncio.create_task(reconcile())
                    try:
                        async for raw in ws:
                            request = json.loads(raw)
                            if request.get('type')!='owner_request':
                                continue
                            async with reader_lock:
                                result = await asyncio.to_thread(self.reader.read,request)
                                files = await asyncio.to_thread(self.reader.scan)
                            # 版本/删除元数据先到 Hub，旧版本正文不得越过最终返回屏障。
                            await send({'type':'owner_manifest','files':files})
                            await send({'type':'owner_response','request_id':request['request_id'],'result':result})
                    finally:
                        ticker.cancel()
                        try:
                            await ticker
                        except asyncio.CancelledError:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception:
                # 禁止输出异常载荷、请求或正文；离线时不排队正文。
                print('Owner read connection unavailable; retrying')
                await asyncio.sleep(5)
