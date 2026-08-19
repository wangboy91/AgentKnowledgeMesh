"""MCP Server 实现.

让 AI Agent (Claude Code, Cursor 等) 通过 MCP 协议访问知识库。

支持的工具：
- search_documents: 搜索文档
- get_document: 获取文档详情
- list_documents: 列出文档
"""

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from sqlalchemy import select, or_

from db import async_session
from models.document import Document


async def handle_list_tools(ctx, params) -> types.ListToolsResult:
    """返回可用工具列表."""
    return types.ListToolsResult(tools=[
        types.Tool(
            name="search_documents",
            description="搜索知识库中的文档。支持关键词搜索，返回相关文档列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
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
        )
    ])


async def handle_call_tool(ctx, params: types.CallToolRequest) -> types.CallToolResult:
    """处理工具调用."""
    name = params.name
    arguments = params.arguments or {}

    if name == "search_documents":
        return await _search_documents(
            query=arguments["query"],
            limit=arguments.get("limit", 5)
        )
    elif name == "get_document":
        return await _get_document(
            document_id=arguments["document_id"]
        )
    elif name == "list_documents":
        return await _list_documents(
            node_id=arguments.get("node_id"),
            limit=arguments.get("limit", 20)
        )
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _search_documents(query: str, limit: int) -> types.CallToolResult:
    """搜索文档."""
    pattern = f"%{query}%"

    async with async_session() as session:
        stmt = (
            select(Document)
            .where(
                or_(
                    Document.title.ilike(pattern),
                    Document.path.ilike(pattern),
                    Document.content.ilike(pattern)
                )
            )
            .order_by(Document.title.ilike(pattern).desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        documents = result.scalars().all()

    if not documents:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"未找到与 '{query}' 相关的文档。")
        ])

    # 格式化结果
    lines = [f"找到 {len(documents)} 个相关文档：\n"]
    for doc in documents:
        lines.append(f"## {doc.title}")
        lines.append(f"- 路径: {doc.path}")
        lines.append(f"- 节点: {doc.node_id}")
        lines.append(f"- 大小: {doc.size / 1024:.1f} KB")
        lines.append(f"- 更新: {doc.updated_at}")
        lines.append("")

    return types.CallToolResult(content=[
        types.TextContent(type="text", text="\n".join(lines))
    ])


async def _get_document(document_id: int) -> types.CallToolResult:
    """获取文档详情."""
    async with async_session() as session:
        doc = await session.get(Document, document_id)

    if not doc:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"文档 ID {document_id} 不存在。")
        ])

    content = f"""# {doc.title}

**路径**: {doc.path}
**节点**: {doc.node_id}
**大小**: {doc.size / 1024:.1f} KB
**更新时间**: {doc.updated_at}

---

{doc.content or '(空文档)'}
"""

    return types.CallToolResult(content=[
        types.TextContent(type="text", text=content)
    ])


async def _list_documents(node_id: str | None, limit: int) -> types.CallToolResult:
    """列出文档."""
    async with async_session() as session:
        stmt = select(Document)

        if node_id:
            stmt = stmt.where(Document.node_id == node_id)

        stmt = stmt.order_by(Document.updated_at.desc()).limit(limit)
        result = await session.execute(stmt)
        documents = result.scalars().all()

    if not documents:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text="暂无文档。")
        ])

    lines = [f"文档列表（共 {len(documents)} 个）：\n"]
    for doc in documents:
        lines.append(f"- [{doc.id}] {doc.title} ({doc.path})")

    return types.CallToolResult(content=[
        types.TextContent(type="text", text="\n".join(lines))
    ])


# 创建 MCP Server 实例
server = Server(
    "agentknowledge-mesh",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def run_mcp_stdio():
    """以 stdio 方式运行 MCP Server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
