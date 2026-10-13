"""严格模式旧全文读取/写入屏障；纯 ASGI，避免 SSE 中间件缓冲。"""
import re
from starlette.responses import JSONResponse
from app.config import settings


class OwnerModeBarrier:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if settings.owner_readonly_enabled:
            path = scope.get('path','')
            root = scope.get('root_path','')
            if root and path.startswith(root+'/'):
                path = path[len(root):]
            blocked = path == '/ws' or any(path==p or path.startswith(p+'/') for p in (
                '/api/documents','/api/search','/api/rag','/api/context','/api/mcp','/api/convert'))
            blocked = blocked or bool(re.match(r'^/api/nodes/[^/]+/(documents|sync)(/|$)',path))
            if blocked:
                if scope['type']=='websocket':
                    await send({'type':'websocket.close','code':1008})
                elif scope['type']=='http':
                    await JSONResponse({'detail':'Legacy content access disabled in owner mode'},status_code=409,
                        headers={'Cache-Control':'no-store'})(scope,receive,send)
                return
        await self.app(scope,receive,send)
