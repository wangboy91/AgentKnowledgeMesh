"""MCP HTTP 端点.

提供基于 SSE (Server-Sent Events) 的 MCP 传输。
让 Claude Code、Cursor 等工具可以通过 HTTP 连接到 MCP Server。
"""

from fastapi import APIRouter, Depends, Request

from app.services.auth import require_auth
from sse_starlette.sse import EventSourceResponse
from mcp.server.sse import SseServerTransport

from app.services.mcp_server import server

router = APIRouter()

# SSE 通告给客户端的消息端点。必须是**实际可用的完整路由路径**:本模块被挂在
# `include_router(router, prefix="/api")` + `include_router(mcp_router, prefix="/mcp")`
# 之下,真实路由是 `POST /api/mcp/messages`。
#
# 历史缺陷:此处原为 "/messages",而 sse 库会把 scope["root_path"] 拼在前面,
# 于是客户端被告知回发到 `/messages` —— 实测 POST /messages 返回 404、而
# POST /api/mcp/messages 返回 202,即按通告地址回发的 MCP 客户端必然失败。
#
# 不含部署前缀:mcp 库用 scope["root_path"] 自动拼上,故子路径部署下
# 通告为 `{AKM_ROOT_PATH}/api/mcp/messages`(见 subpath-deployment)。
MESSAGES_PATH = "/api/mcp/messages"

# SSE 传输实例
sse_transport = SseServerTransport(MESSAGES_PATH)


@router.get("/sse")
async def mcp_sse(request: Request, principal=Depends(require_auth("viewer"))):
    """SSE 端点 - 建立长期连接.

    客户端连接此端点接收服务器推送的消息。
    """
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send,
    ) as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


@router.post("/messages")
async def mcp_messages(request: Request, principal=Depends(require_auth("viewer"))):
    """消息端点 - 接收客户端请求.

    客户端通过 POST 发送请求到此端点。
    """
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send,
    )
