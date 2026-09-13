"""MCP server 语义检索分支测试(mode=semantic).

覆盖 handle_call_tool → search_documents(mode=semantic) 的:
- search_hybrid 命中结果经共享格式化输出(与节点代理一致)
- 向量检索异常降级为 isError 错误文本,不崩溃

语义分支会查询 rag_status 排除集(真实 DB),autouse 桩隔离避免触达真实库。
"""

import pytest_asyncio
import mcp.types as types

from app.services import mcp_server


class _FakeResult:
    def all(self):
        return []


class _FakeSession:
    async def execute(self, *a, **k):
        return _FakeResult()


class _FakeCtx:
    async def __aenter__(self):
        return _FakeSession()

    async def __aexit__(self, *a):
        return False


@pytest_asyncio.fixture(autouse=True)
def _stub_db_session(monkeypatch):
    """隔离 mcp_server 语义分支的 rag_status 查询(不触真实库)."""
    monkeypatch.setattr("app.services.mcp_server.async_session", lambda: _FakeCtx())


async def _call(name, arguments):
    return await mcp_server.handle_call_tool(
        None, types.CallToolRequestParams(name=name, arguments=arguments)
    )


async def test_semantic_search_hit_formats(monkeypatch):
    """mode=semantic:经混合检索并输出带分数的语义格式."""
    monkeypatch.setattr(
        "app.services.rag.vector_store.search_hybrid",
        lambda query, limit, node_id=None, excluded_doc_ids=None: [
            {"doc_id": 1, "title": "Alpha", "path": "kb/a.md", "node_id": "n",
             "chunk": "命中分块内容", "score": 0.7},
        ],
    )

    result = await _call("search_documents", {"query": "q", "mode": "semantic"})

    assert not result.is_error
    text = result.content[0].text
    assert "1 个语义相关文档" in text
    assert "分数: 0.7000" in text
    assert "命中分块内容" in text


async def test_semantic_search_null(monkeypatch):
    """语义无命中 → 空结果文案."""
    monkeypatch.setattr(
        "app.services.rag.vector_store.search_hybrid",
        lambda query, limit, node_id=None, excluded_doc_ids=None: [],
    )

    result = await _call("search_documents", {"query": "ghost", "mode": "semantic"})

    assert "未找到与 'ghost' 语义相关的文档。" == result.content[0].text


async def test_semantic_search_vector_error_degrades(monkeypatch):
    """向量库异常 → isError 错误文本,进程不崩."""
    def _boom(query, limit, node_id=None, excluded_doc_ids=None):
        raise RuntimeError("pgvector unavailable")

    monkeypatch.setattr("app.services.rag.vector_store.search_hybrid", _boom)

    result = await _call("search_documents", {"query": "q", "mode": "semantic"})

    assert result.is_error
    assert "语义检索失败" in result.content[0].text