"""MCP HTTP 端点.

提供基于 SSE (Server-Sent Events) 的 MCP 传输。
让 Claude Code、Cursor 等工具可以通过 HTTP 连接到 MCP Server。
"""

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from mcp.server.sse import SseServerTransport

from app.services.mcp_server import server

router = APIRouter()

# SSE 传输实例
sse_transport = SseServerTransport("/messages")


@router.get("/sse")
async def mcp_sse(request: Request):
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
async def mcp_messages(request: Request):
    """消息端点 - 接收客户端请求.

    客户端通过 POST 发送请求到此端点。
    """
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send,
    )
