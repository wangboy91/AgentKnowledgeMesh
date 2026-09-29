"""MCP server 语义检索分支测试(mode=semantic).

覆盖 handle_call_tool → search_documents(mode=semantic) 的:
- search_hybrid 命中结果经共享格式化输出(与节点代理一致)
- 向量检索异常降级为 isError 错误文本,不崩溃
- 向量化总开关关闭时降级为关键词检索并标注,不访问向量库

语义分支会查询 app_settings 与 rag_status(真实 DB),autouse 桩隔离避免触达真实库。
"""

import pytest_asyncio
import mcp.types as types

from app.services import mcp_server


class _FakeResult:
    def all(self):
        return []

    def scalars(self):
        """关键词分支走 result.scalars().all()."""
        return self


class _FakeSetting:
    """app_settings 桩(向量化总开关)."""

    def __init__(self, value: str):
        self.value = value


class _FakeSession:
    def __init__(self, vectorization_enabled: bool = True):
        self._vectorization_enabled = vectorization_enabled

    async def execute(self, *a, **k):
        return _FakeResult()

    async def get(self, model, key, *a, **k):
        return _FakeSetting("true" if self._vectorization_enabled else "false")


class _FakeCtx:
    def __init__(self, vectorization_enabled: bool = True):
        self._vectorization_enabled = vectorization_enabled

    async def __aenter__(self):
        return _FakeSession(self._vectorization_enabled)

    async def __aexit__(self, *a):
        return False


@pytest_asyncio.fixture(autouse=True)
def _stub_db_session(monkeypatch):
    """隔离 mcp_server 的设置与 rag_status 查询(不触真实库);默认向量化开启."""
    monkeypatch.setattr("app.services.mcp_server.async_session", lambda: _FakeCtx())


@pytest_asyncio.fixture
def vectorization_disabled(_stub_db_session, monkeypatch):
    """把向量化总开关置为关闭."""
    monkeypatch.setattr(
        "app.services.mcp_server.async_session",
        lambda: _FakeCtx(vectorization_enabled=False),
    )


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


async def test_semantic_search_degrades_when_vectorization_disabled(
    vectorization_disabled, monkeypatch
):
    """向量化关闭 → 降级关键词检索并标注,不访问向量库、不报错."""
    def _boom(query, limit, node_id=None, excluded_doc_ids=None):
        raise AssertionError("向量化关闭时不应访问向量库")

    monkeypatch.setattr("app.services.rag.vector_store.search_hybrid", _boom)

    result = await _call("search_documents", {"query": "q", "mode": "semantic"})

    assert not result.is_error
    assert "已降级为关键词检索" in result.content[0].text