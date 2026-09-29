"""MCP Server 实现.

让 AI Agent (Claude Code, Cursor 等) 通过 MCP 协议访问知识库。

支持的工具：
- search_documents: 搜索文档
- get_document: 获取文档详情
- list_documents: 列出文档
- create_document: 新建文档(智能体写回)
- update_document: 覆盖更新文档正文(智能体写回)

写工具的归属固定为 `local`(Hub 本机信任形态);节点凭证的写回经节点本地
代理走 REST(见 `app/api/documents.py`),由服务端依据节点凭证强制作用域。
"""

import asyncio

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from sqlalchemy import select, or_

from akm_shared.mcp_formatting import (
    format_document_created,
    format_document_detail,
    format_document_list,
    format_document_updated,
    format_search_results,
    format_semantic_search,
)

from app.db import async_session
from app.models.document import Document
from app.services.document_writer import upsert_payload as _upsert_payload

# 后台向量维护任务的强引用集合:asyncio 不持有 task 的强引用,不保留会被 GC 回收
_background_tasks: set[asyncio.Task] = set()


def _spawn_index(upserts: list[dict]) -> None:
    """后台派发向量维护(失败仅告警,不影响工具响应)."""
    from app.services.rag.sync import sync_index_and_mark

    task = asyncio.create_task(sync_index_and_mark(upserts, []))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def handle_list_tools(ctx, params) -> types.ListToolsResult:
    """返回可用工具列表."""
    return types.ListToolsResult(tools=[
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
        types.Tool(
            name="create_document",
            description="在知识库中新建一篇 Markdown 文档。路径已存在时返回冲突错误，此时应改用 update_document。",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文档相对路径，如 notes/foo.md"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown 全文"
                    },
                    "title": {
                        "type": "string",
                        "description": "标题（可选；缺省或为空时从内容首行 # 或路径文件名提取）"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        types.Tool(
            name="update_document",
            description="覆盖更新已有文档的正文。文档 ID 可由 search_documents / list_documents 获得；文档不存在时返回错误。",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "integer",
                        "description": "文档 ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "新的 Markdown 全文"
                    }
                },
                "required": ["document_id", "content"]
            }
        )
    ])


async def handle_call_tool(ctx, params: types.CallToolRequest) -> types.CallToolResult:
    """处理工具调用."""
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
                document_id=arguments["document_id"]
            )
        elif name == "list_documents":
            return await _list_documents(
                node_id=arguments.get("node_id"),
                limit=arguments.get("limit", 20)
            )
        elif name == "create_document":
            return await _create_document(
                path=arguments["path"],
                content=arguments["content"],
                title=arguments.get("title"),
            )
        elif name == "update_document":
            return await _update_document(
                document_id=arguments["document_id"],
                content=arguments["content"],
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
    except KeyError as e:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"缺少参数: {e.args[0]}")
        ], isError=True)


async def _search_documents(query: str, limit: int, mode: str = "keyword") -> types.CallToolResult:
    """搜索文档.

    keyword:文档表 LIKE 检索;semantic:dense+sparse 混合向量检索(质量由 Hub 保证)。
    向量化总开关关闭时 semantic 降级为 keyword,并在输出首行标注降级原因。
    """
    degraded_note = ""
    if mode == "semantic":
        from app.services.rag import vector_store
        from app.services.rag.sync import get_vectorization_enabled

        async with async_session() as session:
            vectorization_enabled = await get_vectorization_enabled(session)

        if vectorization_enabled:
            try:
                # 仅召回 rag_status 为 indexed 的文档(与 /api/rag/search 一致)
                async with async_session() as session:
                    stmt = select(Document.id).where(Document.rag_status != "indexed")
                    excluded = {row[0] for row in (await session.execute(stmt)).all()}
                results = vector_store.search_hybrid(
                    query=query, limit=limit, excluded_doc_ids=excluded,
                )
            except Exception as e:
                return types.CallToolResult(content=[
                    types.TextContent(type="text", text=f"语义检索失败:{e}")
                ], isError=True)
            text = format_semantic_search(query, results)
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=text)
            ])

        # 关闭时降级:继续走下面的关键词分支,输出前加提示
        degraded_note = "（向量化未开启，已降级为关键词检索）\n"

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
            .order_by(
                # 标题匹配优先,更新时间次序(与 /api/search 保持一致,三形态输出稳定)
                Document.title.ilike(pattern).desc(),
                Document.updated_at.desc(),
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        documents = result.scalars().all()

    if not documents:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"{degraded_note}未找到与 '{query}' 相关的文档。")
        ])

    # 格式化逻辑单源共享(与节点本地代理输出一致)
    docs = [doc.to_dict(include_content=False) for doc in documents]
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=degraded_note + format_search_results(query, docs))
    ])


async def _get_document(document_id: int) -> types.CallToolResult:
    """获取文档详情."""
    async with async_session() as session:
        doc = await session.get(Document, document_id)

    if not doc:
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"文档 ID {document_id} 不存在。")
        ])

    return types.CallToolResult(content=[
        types.TextContent(type="text", text=format_document_detail(doc.to_dict(include_content=True)))
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

    docs = [doc.to_dict(include_content=False) for doc in documents]
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=format_document_list(docs))
    ])


async def _create_document(path: str, content: str, title: str | None = None) -> types.CallToolResult:
    """新建文档(归属 `local`;与 REST `POST /api/documents` 同一写入口径)."""
    from app.services.document_writer import PathConflict
    from app.services.document_writer import create_document as write_create

    async with async_session() as session:
        try:
            doc = await write_create(
                session, node_id="local", path=path, content=content, title=title
            )
        except PathConflict:
            existing = await session.execute(
                select(Document).where(Document.node_id == "local", Document.path == path)
            )
            hit = existing.scalar_one_or_none()
            hint = f"(文档 ID {hit.id})" if hit else ""
            return types.CallToolResult(content=[types.TextContent(
                type="text",
                text=f"路径已存在:{path}{hint},请改用 update_document。",
            )])
        payload = doc.to_dict()
        upsert = _upsert_payload(doc) if doc.rag_status == "indexed" else None

    if upsert:
        _spawn_index([upsert])
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=format_document_created(payload))
    ])


async def _update_document(document_id: int, content: str) -> types.CallToolResult:
    """覆盖更新文档正文(与 REST `PUT /api/documents/{id}` 同一写入口径)."""
    from app.services.document_writer import update_document as write_update

    async with async_session() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return types.CallToolResult(content=[types.TextContent(
                type="text", text=f"文档 ID {document_id} 不存在。"
            )])
        doc = await write_update(session, doc, content)
        payload = doc.to_dict()
        upsert = _upsert_payload(doc) if doc.rag_status == "indexed" else None

    if upsert:
        _spawn_index([upsert])
    return types.CallToolResult(content=[
        types.TextContent(type="text", text=format_document_updated(payload))
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
