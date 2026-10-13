"""owner 严格模式的内存 RPC；只转发实时正文，不持久排队或记录载荷。"""
import asyncio
import uuid


class OwnerGateway:
    def __init__(self):
        self.connections = {}
        self.pending = {}
        self.send_locks = {}

    def connect(self, owner, websocket):
        if owner in self.connections:
            raise ValueError('owner already connected')
        self.connections[owner] = websocket
        self.send_locks[owner] = asyncio.Lock()

    def disconnect(self, owner, websocket):
        if self.connections.get(owner) is not websocket:
            return
        self.connections.pop(owner, None)
        self.send_locks.pop(owner, None)
        for key, (bound_owner, future) in list(self.pending.items()):
            if bound_owner == owner and not future.done():
                future.set_exception(ConnectionError('owner offline'))

    async def request(self, owner, payload, timeout):
        websocket = self.connections.get(owner)
        if websocket is None:
            raise ConnectionError('owner offline')
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = (owner, future)
        try:
            try:
                lock = self.send_locks.get(owner)
                if lock is None:
                    raise ConnectionError('owner offline')
                async with lock:
                    await websocket.send_json({'type':'owner_request','request_id':request_id, **payload})
            except Exception:
                raise ConnectionError('owner transport unavailable') from None
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    def reply(self, owner, websocket, request_id, result):
        hit = self.pending.get(request_id)
        if self.connections.get(owner) is websocket and hit and hit[0] == owner and not hit[1].done():
            hit[1].set_result(result)


gateway = OwnerGateway()
