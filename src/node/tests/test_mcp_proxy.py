"""节点本地 MCP 代理单测(app/mcp_proxy.py + akm_shared.mcp_formatting).

覆盖:
- 格式化函数:命中 / 空结果 / 空文档(与 Hub MCP 输出格式一致)
- 工具转调:search / get / list 成功路径与本地过滤截断
- 工具转调:create / update 写回(方法 / 路径 / body,不携带 node_id)
- 错误映射:连接失败 / 401 凭证失效 / 超时 → isError 文本,进程不崩溃
- 写回错误映射:409 路径冲突 / 403 越权 / 404 不存在
"""

import httpx
import mcp.types as types

from akm_shared.mcp_formatting import (
    format_document_created,
    format_document_detail,
    format_document_list,
    format_document_updated,
    format_search_results,
    format_semantic_search,
)


def _hit_doc(**overrides):
    doc = {
        "id": 1,
        "node_id": "node-1",
        "path": "kb/a.md",
        "title": "Alpha",
        "hash": "h",
        "size": 2048,
        "tags": [],
        "created_at": "2026-09-11T00:00:00",
        "updated_at": "2026-09-11T00:00:00",
        "content": "# Alpha\n\nbody",
    }
    doc.update(overrides)
    return doc


# ---- 格式化函数(2.1) ----

def test_format_search_results_hit():
    text = format_search_results("alpha", [_hit_doc()])
    assert "找到 1 个相关文档" in text
    assert "## Alpha" in text
    assert "- 路径: kb/a.md" in text
    assert "- 节点: node-1" in text
    assert "- 大小: 2.0 KB" in text


def test_format_search_results_empty():
    assert format_search_results("ghost", []) == "未找到与 'ghost' 相关的文档。"


def test_format_document_detail_full():
    text = format_document_detail(_hit_doc())
    assert text.startswith("# Alpha")
    assert "**路径**: kb/a.md" in text
    assert "---" in text
    assert "body" in text


def test_format_document_detail_empty_content():
    text = format_document_detail(_hit_doc(content=None))
    assert "(空文档)" in text


def test_format_document_list_hit():
    text = format_document_list([_hit_doc(), _hit_doc(id=2, title="Beta", path="kb/b.md")])
    assert "文档列表（共 2 个）" in text
    assert "- [1] Alpha (kb/a.md)" in text
    assert "- [2] Beta (kb/b.md)" in text


def test_format_document_list_empty():
    assert format_document_list([]) == "暂无文档。"


def test_format_semantic_search_hit():
    text = format_semantic_search(
        "一个问题",
        [{"doc_id": 1, "title": "T", "path": "kb/a.md", "node_id": "n",
          "chunk": "命中分块内容", "score": 0.5}],
    )
    assert "1 个语义相关文档" in text
    assert "分数: 0.5000" in text
    assert "命中分块内容" in text


def test_format_semantic_search_empty():
    assert format_semantic_search("一个问题", []) == "未找到与 '一个问题' 语义相关的文档。"


# ---- 工具转调与错误映射(2.1 / 2.2) ----

from app.mcp_proxy import _get_document, _list_documents, _search_documents  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        return self._body


def _patch_hub_get(monkeypatch, responses):
    """让 _hub_get 返回预设响应或抛出预设异常(循环复用),记录调用路径供路由断言."""
    import itertools

    import app.mcp_proxy as proxy

    calls = []
    pool = itertools.cycle(responses)

    async def fake_hub_get(path, params=None):
        calls.append((path, params))
        result = next(pool)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(proxy, "_hub_get", fake_hub_get)
    return calls


async def test_search_documents_success(monkeypatch):
    _patch_hub_get(monkeypatch, [
        _FakeResponse(200, {"query": "alpha", "count": 1, "documents": [_hit_doc()]})
    ])

    result = await _search_documents("alpha", 5)

    assert not result.is_error
    assert "找到 1 个相关文档" in result.content[0].text
    assert "## Alpha" in result.content[0].text


async def test_search_documents_empty(monkeypatch):
    _patch_hub_get(monkeypatch, [
        _FakeResponse(200, {"query": "ghost", "count": 0, "documents": []})
    ])

    result = await _search_documents("ghost", 5)

    assert "未找到与 'ghost' 相关的文档。" == result.content[0].text


async def test_get_document_success(monkeypatch):
    _patch_hub_get(monkeypatch, [_FakeResponse(200, _hit_doc())])

    result = await _get_document(1)

    assert result.content[0].text.startswith("# Alpha")
    assert "body" in result.content[0].text


async def test_get_document_not_found(monkeypatch):
    _patch_hub_get(monkeypatch, [_FakeResponse(404, {"detail": "Document not found"})])

    result = await _get_document(999)

    assert not result.is_error  # 业务性"不存在"与 Hub 一致,非基础设施错误
    assert "文档 ID 999 不存在。" == result.content[0].text


async def test_list_documents_filter_and_limit(monkeypatch):
    docs = [
        _hit_doc(id=1, node_id="node-1"),
        _hit_doc(id=2, node_id="node-2"),
        _hit_doc(id=3, node_id="node-1"),
        _hit_doc(id=4, node_id="node-1"),
    ]
    _patch_hub_get(monkeypatch, [_FakeResponse(200, docs)])

    result = await _list_documents(node_id="node-1", limit=2)

    text = result.content[0].text
    assert "文档列表（共 2 个）" in text
    assert "[1] Alpha" in text
    assert "[3] Alpha" in text
    assert "[2]" not in text and "[4]" not in text


async def test_list_documents_no_filter(monkeypatch):
    docs = [_hit_doc(id=1), _hit_doc(id=2, node_id="node-2")]
    _patch_hub_get(monkeypatch, [_FakeResponse(200, docs)])

    result = await _list_documents(node_id=None, limit=20)

    assert "文档列表（共 2 个）" in result.content[0].text


async def test_hub_unreachable_maps_to_error(monkeypatch):
    """连接失败 → "无法连接 Hub",isError,进程不崩溃."""
    _patch_hub_get(monkeypatch, [httpx.ConnectError("conn refused")])

    for call in (
        lambda: _search_documents("x", 5),
        lambda: _get_document(1),
        lambda: _list_documents(None, 20),
    ):
        result = await call()
        assert result.is_error
        assert "无法连接 Hub" in result.content[0].text
        assert "请检查 Hub 状态" in result.content[0].text


async def test_unauthorized_maps_to_relogin_hint(monkeypatch):
    """401 → "凭证已失效,请重新执行 akm-node login"."""
    _patch_hub_get(monkeypatch, [_FakeResponse(401, {"detail": "Invalid token"})])

    for call in (
        lambda: _search_documents("x", 5),
        lambda: _get_document(1),
        lambda: _list_documents(None, 20),
    ):
        result = await call()
        assert result.is_error
        assert "凭证已失效" in result.content[0].text
        assert "akm-node login" in result.content[0].text


async def test_timeout_maps_to_retry_hint(monkeypatch):
    """超时 → 明确提示,不崩溃."""
    _patch_hub_get(monkeypatch, [httpx.ReadTimeout("timed out")])

    result = await _search_documents("x", 5)

    assert result.is_error
    assert "超时" in result.content[0].text


async def test_hub_500_maps_to_error(monkeypatch):
    _patch_hub_get(monkeypatch, [_FakeResponse(500, text="internal error")])

    result = await _search_documents("x", 5)

    assert result.is_error
    assert "Hub 返回错误(500)" in result.content[0].text


async def test_search_semantic_forwards_and_formats(monkeypatch):
    """mode=semantic:转发 /rag/search 并格式化(含分数与命中分块)."""
    calls = _patch_hub_get(monkeypatch, [
        _FakeResponse(200, {"query": "一个问题", "count": 1, "results": [
            {"doc_id": 1, "title": "Alpha", "path": "kb/a.md", "node_id": "n",
             "chunk": "相关分块内容", "score": 0.82}
        ]})
    ])

    result = await _search_documents("一个问题", 5, mode="semantic")

    assert calls[0][0] == "/rag/search"
    assert calls[0][1] == {"q": "一个问题", "limit": 5}
    assert not result.is_error
    text = result.content[0].text
    assert "语义相关文档" in text
    assert "分数: 0.8200" in text
    assert "相关分块内容" in text


async def test_search_keyword_is_default_route(monkeypatch):
    """缺省 mode:仍走 /search 关键词端点(行为不回退)."""
    calls = _patch_hub_get(monkeypatch, [
        _FakeResponse(200, {"query": "x", "count": 1, "documents": [_hit_doc()]})
    ])

    await _search_documents("x", 5)

    assert calls[0][0] == "/search"


async def test_search_semantic_error_field(monkeypatch):
    """语义端点返回 error 字段 → 明确错误文本(isError)."""
    _patch_hub_get(monkeypatch, [
        _FakeResponse(200, {
            "query": "x", "count": 0, "results": [],
            "error": "connection to vector db failed",
        })
    ])

    result = await _search_documents("x", 5, mode="semantic")

    assert result.is_error
    assert "语义检索失败" in result.content[0].text


# ---- 写回工具:格式化函数 ----

def test_format_document_created():
    text = format_document_created(_hit_doc())
    assert "已创建文档 [1] Alpha" in text
    assert "- 路径: kb/a.md" in text
    assert "- 节点: node-1" in text
    assert "- 大小: 2.0 KB" in text


def test_format_document_updated():
    text = format_document_updated(_hit_doc())
    assert "已更新文档 [1] Alpha" in text
    assert "- 更新时间: 2026-09-11T00:00:00" in text


# ---- 写回工具:转调与错误映射 ----

from app.mcp_proxy import _create_document, _update_document  # noqa: E402


def _patch_hub_write(monkeypatch, responses):
    """让 _hub_write 返回预设响应或抛预设异常(循环复用),记录 (method, path, json)."""
    import itertools

    import app.mcp_proxy as proxy

    calls = []
    pool = itertools.cycle(responses)

    async def fake_hub_write(method, path, json):
        calls.append((method, path, json))
        result = next(pool)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(proxy, "_hub_write", fake_hub_write)
    return calls


async def test_create_document_forwards_without_node_id(monkeypatch):
    """create → POST /documents;请求体不得携带 node_id(归属由 Hub 强制)."""
    calls = _patch_hub_write(monkeypatch, [_FakeResponse(200, _hit_doc())])

    result = await _create_document("kb/a.md", "# Alpha\n\nbody", title="Alpha")

    assert calls[0][0] == "POST"
    assert calls[0][1] == "/documents"
    body = calls[0][2]
    assert body == {"path": "kb/a.md", "content": "# Alpha\n\nbody", "title": "Alpha"}
    assert "node_id" not in body
    assert not result.is_error
    assert "已创建文档 [1] Alpha" in result.content[0].text


async def test_create_document_without_title_omits_key(monkeypatch):
    calls = _patch_hub_write(monkeypatch, [_FakeResponse(200, _hit_doc())])

    await _create_document("kb/a.md", "# Alpha")

    assert "title" not in calls[0][2]


async def test_create_document_conflict_text(monkeypatch):
    """409 → 业务性冲突文本(非基础设施错误),提示改用 update_document."""
    _patch_hub_write(monkeypatch, [_FakeResponse(409, {"detail": "exists"})])

    result = await _create_document("kb/a.md", "# A")

    assert not result.is_error
    assert "路径已存在" in result.content[0].text
    assert "update_document" in result.content[0].text


async def test_create_document_forbidden_text(monkeypatch):
    """403 → 越权文本."""
    _patch_hub_write(monkeypatch, [_FakeResponse(403, {"detail": "forbidden"})])

    result = await _create_document("kb/a.md", "# A")

    assert not result.is_error
    assert "无权写入" in result.content[0].text


async def test_update_document_forwards(monkeypatch):
    """update → PUT /documents/{id};body 仅 content."""
    calls = _patch_hub_write(monkeypatch, [_FakeResponse(200, _hit_doc())])

    result = await _update_document(1, "# Alpha v2")

    assert calls[0] == ("PUT", "/documents/1", {"content": "# Alpha v2"})
    assert not result.is_error
    assert "已更新文档 [1] Alpha" in result.content[0].text


async def test_update_document_not_found_text(monkeypatch):
    _patch_hub_write(monkeypatch, [_FakeResponse(404, {"detail": "Document not found"})])

    result = await _update_document(999, "x")

    assert not result.is_error
    assert "文档 ID 999 不存在。" == result.content[0].text


async def test_update_document_forbidden_text(monkeypatch):
    _patch_hub_write(monkeypatch, [_FakeResponse(403, {"detail": "forbidden"})])

    result = await _update_document(1, "x")

    assert not result.is_error
    assert "无权修改该文档" in result.content[0].text


async def test_write_hub_unreachable_maps_to_error(monkeypatch):
    """写通道连接失败 → isError + 可操作文本,进程不崩溃."""
    _patch_hub_write(monkeypatch, [httpx.ConnectError("conn refused")])

    for call in (
        lambda: _create_document("kb/a.md", "# A"),
        lambda: _update_document(1, "x"),
    ):
        result = await call()
        assert result.is_error
        assert "无法连接 Hub" in result.content[0].text


async def test_write_unauthorized_maps_to_relogin_hint(monkeypatch):
    _patch_hub_write(monkeypatch, [_FakeResponse(401, {"detail": "Invalid token"})])

    result = await _update_document(1, "x")

    assert result.is_error
    assert "凭证已失效" in result.content[0].text
    assert "akm-node login" in result.content[0].text


async def test_write_timeout_maps_to_retry_hint(monkeypatch):
    _patch_hub_write(monkeypatch, [httpx.ReadTimeout("timed out")])

    result = await _create_document("kb/a.md", "# A")

    assert result.is_error
    assert "超时" in result.content[0].text


async def test_write_hub_500_maps_to_error(monkeypatch):
    _patch_hub_write(monkeypatch, [_FakeResponse(500, text="internal error")])

    result = await _create_document("kb/a.md", "# A")

    assert result.is_error
    assert "Hub 返回错误(500)" in result.content[0].text


# ---- 写回工具:分发与缺参数 ----

async def test_handle_call_tool_dispatches_create(monkeypatch):
    _patch_hub_write(monkeypatch, [_FakeResponse(200, _hit_doc())])

    from app.mcp_proxy import handle_call_tool

    result = await handle_call_tool(
        None,
        types.CallToolRequestParams(
            name="create_document", arguments={"path": "kb/a.md", "content": "# A"}
        ),
    )

    assert "已创建文档" in result.content[0].text


async def test_handle_call_tool_missing_param(monkeypatch):
    """缺必填参数 → "缺少参数: <名称>",不崩溃."""
    from app.mcp_proxy import handle_call_tool

    result = await handle_call_tool(
        None,
        types.CallToolRequestParams(name="update_document", arguments={"content": "x"}),
    )

    assert result.is_error
    assert "缺少参数: document_id" in result.content[0].text


def test_tools_expose_write_tools():
    """工具清单含写工具,且与 Hub 同名同参(五工具)."""
    from app.mcp_proxy import TOOLS

    names = [t.name for t in TOOLS]
    assert names == [
        "search_documents",
        "get_document",
        "list_documents",
        "create_document",
        "update_document",
    ]
    schemas = {t.name: t.model_dump(by_alias=True)["inputSchema"] for t in TOOLS}
    assert set(schemas["create_document"]["required"]) == {"path", "content"}
    assert set(schemas["update_document"]["required"]) == {"document_id", "content"}