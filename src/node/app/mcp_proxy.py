"""节点本地 MCP 代理(akm-node --mcp).

以 stdio 向本机智能体提供与 Hub MCP 同名同参的三个工具:
search_documents / get_document / list_documents。
内部转调 Hub HTTP API(复用节点凭证,统一 10s 超时);节点不做本地
向量检索,语义质量由 Hub 保证。连接失败/凭证失效/超时映射为明确
错误文本(isError 标记),MCP 会话保持可用,进程不崩溃。

本模块不使用 print/stdout 诊断输出,避免污染 MCP stdio 协议流。
"""

from __future__ import annotations

import asyncio

import httpx
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from akm_shared.mcp_formatting import (
    format_document_detail,
    format_document_list,
    format_search_results,
    format_semantic_search,
)

from app.config import settings

# 与 Hub MCP(app/services/mcp_server.py)完全一致的工具定义,改动需两侧同步
TOOLS = [
    types.Tool(
        name="search_documents",
        description="搜索知识库中的文档。支持关键词搜索与语义检索(mode=semantic)，返回相关文档列表。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "mode": {
                    "type": "string",
                    "description": "检索方式：keyword(默认，关键词) / semantic(语义，向量检索)",
                    "enum": ["keyword", "semantic"],
                    "default": "keyword"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),
    types.Tool(
        name="get_document",
        description="获取指定文档的完整内容。通过文档 ID 获取。",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "integer",
                    "description": "文档 ID"
                }
            },
            "required": ["document_id"]
        }
    ),
    types.Tool(
        name="list_documents",
        description="列出知识库中的文档。可按节点过滤。",
        inputSchema={
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "节点 ID（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量，默认 20",
                    "default": 20
                }
            }
        }
    ),
]

HUB_TIMEOUT_SECONDS = 10.0


def _error_result(text: str) -> types.CallToolResult:
    """基础设施类错误的统一返回(isError 标记,文本可操作)."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=True,
    )


async def _hub_get(path: str, params: dict | None = None) -> httpx.Response:
    """请求 Hub API(统一超时与节点凭证).

    hub_api_url 约定含 /api 前缀(如 http://host:port/api),path 请传
    "/search"、"/documents/{id}" 这类端点相对路径。
    """
    async with httpx.AsyncClient(timeout=HUB_TIMEOUT_SECONDS) as client:
        return await client.get(
            f"{settings.hub_api_url.rstrip('/')}{path}",
            params=params,
            headers={"Authorization": f"Bearer {settings.node_token}"},
        )


async def _safe_hub_get(path: str, params: dict | None = None):
    """请求 Hub 并把连接/超时/鉴权错误映射为工具错误文本.

    返回 (response, None) 或 (None, error_result);进程不崩溃,会话保持。
    """
    try:
        resp = await _hub_get(path, params)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return None, _error_result(
            f"无法连接 Hub({settings.hub_api_url}):请检查 Hub 状态"
        )
    except httpx.TimeoutException:
        return None, _error_result(
            f"Hub 响应超时({HUB_TIMEOUT_SECONDS:g}s),请稍后重试"
        )
    if resp.status_code == 401:
        return None, _error_result("节点凭证已失效,请重新执行 akm-node login")
    return resp, None


async def _search_documents(query: str, limit: int, mode: str = "keyword") -> types.CallToolResult:
    """search_documents → GET /api/search(关键词)或 /api/rag/search(语义)."""
    if mode == "semantic":
        resp, err = await _safe_hub_get("/rag/search", params={"q": query, "limit": limit})
        if err:
            return err
        if resp.status_code != 200:
            return _error_result(f"Hub 返回错误({resp.status_code}):{resp.text[:200]}")
        data = resp.json()
        if data.get("error"):
            return _error_result(f"语义检索失败:{data['error']}")
        text = format_semantic_search(data.get("query", query), data.get("results", []))
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)])

    resp, err = await _safe_hub_get("/search", params={"q": query, "limit": limit})
    if err:
        return err
    if resp.status_code != 200:
        return _error_result(f"Hub 返回错误({resp.status_code}):{resp.text[:200]}")
    data = resp.json()
    text = format_search_results(data.get("query", query), data.get("documents", []))
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


async def _get_document(document_id: int) -> types.CallToolResult:
    """get_document → GET /api/documents/{id}."""
    resp, err = await _safe_hub_get(f"/documents/{document_id}")
    if err:
        return err
    if resp.status_code == 404:
        # 业务性"不存在"与 Hub 一致用普通文本,不算基础设施错误
        return types.CallToolResult(content=[types.TextContent(
            type="text", text=f"文档 ID {document_id} 不存在。"
        )])
    if resp.status_code != 200:
        return _error_result(f"Hub 返回错误({resp.status_code}):{resp.text[:200]}")
    text = format_document_detail(resp.json())
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


async def _list_documents(node_id: str | None, limit: int) -> types.CallToolResult:
    """list_documents → GET /api/documents(REST 无过滤参数,本地按 node_id 过滤与截断)."""
    resp, err = await _safe_hub_get("/documents")
    if err:
        return err
    if resp.status_code != 200:
        return _error_result(f"Hub 返回错误({resp.status_code}):{resp.text[:200]}")
    documents = resp.json()
    if node_id:
        documents = [d for d in documents if d.get("node_id") == node_id]
    documents = documents[:limit]
    text = format_document_list(documents)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


async def handle_list_tools(ctx, params) -> types.ListToolsResult:
    """返回可用工具列表(与 Hub MCP 一致)."""
    return types.ListToolsResult(tools=TOOLS)


async def handle_call_tool(ctx, params: types.CallToolRequest) -> types.CallToolResult:
    """处理工具调用(分发与 Hub 相同)."""
    name = params.name
    arguments = params.arguments or {}

    try:
        if name == "search_documents":
            return await _search_documents(
                query=arguments["query"],
                limit=arguments.get("limit", 5),
                mode=arguments.get("mode", "keyword"),
            )
        elif name == "get_document":
            return await _get_document(
                document_id=arguments["document_id"],
            )
        elif name == "list_documents":
            return await _list_documents(
                node_id=arguments.get("node_id"),
                limit=arguments.get("limit", 20),
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
    except KeyError as e:
        return _error_result(f"缺少参数: {e.args[0]}")


# 创建 MCP Server 实例(与 Hub 同名,三形态一致)
server = Server(
    "agentknowledge-mesh",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def run_mcp_proxy():
    """以 stdio 方式运行节点本地 MCP 代理."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
