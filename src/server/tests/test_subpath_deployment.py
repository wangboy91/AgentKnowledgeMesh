"""子路径部署(subpath-deployment)测试.

覆盖:
- 前缀规范化(`normalize_root_path` 与 `Settings` 侧容错)
- `index.html` 注入产物(根路径 / 单层 / 多层前缀)
- 两种反代写法下的路由匹配(代理剥离前缀、代理保留前缀)
- SPA 回退注入、静态文件原样返回
- MCP SSE 通告的消息端点必须是真实可用的路由
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.mcp import MESSAGES_PATH
from app.config import Settings, normalize_root_path
from app.main import create_app
from app import main as main_module


# ---------------------------------------------------------------- 前缀规范化


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("/", ""),
        ("akm", "/akm"),
        ("/akm", "/akm"),
        ("/akm/", "/akm"),
        ("/akm///", "/akm"),
        ("  /akm  ", "/akm"),
        ("/a/b/", "/a/b"),
        ("/a/b/c", "/a/b/c"),
    ],
)
def test_normalize_root_path(raw, expected):
    assert normalize_root_path(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [("/akm/", "/akm"), ("", ""), ("akm", "/akm")])
def test_settings_normalizes_root_path(raw, expected):
    """配置项容错:用户写成 akm / /akm/ / 都应归一."""
    assert Settings(root_path=raw).root_path == expected


def test_root_path_defaults_to_empty():
    """缺省为空 = 根路径部署(行为与引入本能力前一致)."""
    assert Settings().root_path == ""


# ---------------------------------------------------------------- 注入产物


INDEX_TEMPLATE = (
    "<!DOCTYPE html><html><head><meta charset=\"UTF-8\" />"
    '<link rel="icon" href="./vault.svg" /></head>'
    '<body><div id="root"></div><script src="./assets/app.js"></script></body></html>'
)


@pytest.fixture
def static_dir(tmp_path, monkeypatch):
    """临时 static/ 目录,并把 main.BASE_DIR 指过去(create_app 按它定位产物)."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (static / "vault.svg").write_text("<svg></svg>", encoding="utf-8")
    (static / "index.html").write_text(INDEX_TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(main_module, "BASE_DIR", tmp_path)
    return static


def make_app(monkeypatch, root_path: str):
    """用指定前缀构造应用(settings 是模块级单例,需替换)."""
    monkeypatch.setattr(main_module, "settings", Settings(root_path=root_path))
    return create_app()


@pytest.mark.parametrize(
    ("root_path", "expected_base"),
    [("", "/"), ("/akm", "/akm/"), ("/a/b/c", "/a/b/c/")],
)
def test_render_index_html_injects_base(static_dir, root_path, expected_base):
    from app.main import render_index_html

    html = render_index_html(static_dir / "index.html", root_path)

    assert f'<base href="{expected_base}" />' in html
    assert f'window.__AKM_BASE__ = "{expected_base}";' in html
    # 注入发生在 <head> 之后、既有 meta 之前
    assert html.index("<base") > html.index("<head>")
    assert html.index("<base") < html.index('charset="UTF-8"')


def test_render_index_html_keeps_original_content(static_dir):
    """注入不得改写原有内容(相对资源引用原样保留,由 <base> 决定解析结果)."""
    from app.main import render_index_html

    html = render_index_html(static_dir / "index.html", "/akm")

    assert '<link rel="icon" href="./vault.svg" />' in html
    assert '<script src="./assets/app.js"></script>' in html


# ---------------------------------------------------------------- 路由匹配


@pytest.mark.asyncio
async def test_routes_match_when_proxy_strips_prefix(static_dir, monkeypatch):
    """代理剥离前缀:应用收到的路径是 /api/health."""
    app = make_app(monkeypatch, "/akm")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_routes_match_when_proxy_keeps_prefix(static_dir, monkeypatch):
    """代理保留前缀:应用收到的路径是 /akm/api/health(Starlette 会剥掉 root_path)."""
    app = make_app(monkeypatch, "/akm")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/akm/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_root_path_deployment_unchanged(static_dir, monkeypatch):
    """根路径部署(缺省):既有路径行为不变."""
    app = make_app(monkeypatch, "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------- SPA 托管


@pytest.mark.asyncio
async def test_spa_fallback_returns_injected_html(static_dir, monkeypatch):
    app = make_app(monkeypatch, "/akm")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/", "/knowledge", "/nodes", "/knowledge/深层/文档.md"):
            resp = await client.get(path)
            assert resp.status_code == 200, path
            assert '<base href="/akm/" />' in resp.text, path


@pytest.mark.asyncio
async def test_spa_fallback_injects_root_base_when_no_prefix(static_dir, monkeypatch):
    app = make_app(monkeypatch, "")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/knowledge")
    assert resp.status_code == 200
    assert '<base href="/" />' in resp.text


@pytest.mark.asyncio
async def test_static_file_returned_verbatim(static_dir, monkeypatch):
    """静态目录中的真实文件原样返回,不注入."""
    app = make_app(monkeypatch, "/akm")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        svg = await client.get("/vault.svg")
        js = await client.get("/assets/app.js")

    assert svg.status_code == 200
    assert svg.text == "<svg></svg>"
    assert "<base" not in svg.text
    assert js.status_code == 200
    assert "console.log" in js.text


@pytest.mark.asyncio
@pytest.mark.parametrize("root_path", ["", "/akm", "/a/b/c"])
async def test_assets_reachable_in_both_proxy_modes(static_dir, monkeypatch, root_path):
    """`/assets/*` 在两种反代写法下都必须命中(回归:曾被 Mount+root_path 打成 404).

    - 代理剥离前缀:应用收到 `/assets/app.js`
    - 代理保留前缀:应用收到 `{root_path}/assets/app.js`

    两种写法都返回同一份产物,因此同一构建产物可挂在任意深度子路径下。
    """
    app = make_app(monkeypatch, root_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stripped = await client.get("/assets/app.js")
        kept = await client.get(f"{root_path}/assets/app.js")

    assert stripped.status_code == 200, "代理剥离前缀时 /assets/app.js 必须命中"
    assert kept.status_code == 200, "代理保留前缀时 /assets/app.js 必须命中"
    assert "console.log" in stripped.text
    assert stripped.text == kept.text


@pytest.mark.asyncio
async def test_static_serving_rejects_path_traversal(static_dir, monkeypatch):
    """`..` 不得逃出 static/ 目录(不得把源码/配置当静态文件吐出去)."""
    from app.main import resolve_static_file

    (static_dir.parent / "secret.txt").write_text("top-secret", encoding="utf-8")
    root = static_dir.resolve()

    assert resolve_static_file(root, "../secret.txt") is None
    assert resolve_static_file(root, "assets/../../secret.txt") is None
    # 正常文件仍可解析
    assert resolve_static_file(root, "assets/app.js") == (root / "assets" / "app.js")
    # 目录不算文件
    assert resolve_static_file(root, "assets") is None
    # index.html 交由 SPA 分支处理(需注入前缀)
    assert resolve_static_file(root, "index.html") is None


@pytest.mark.asyncio
async def test_index_html_entry_not_double_injected(static_dir, monkeypatch):
    """直接请求 /index.html 也走注入版(且只注入一次)."""
    app = make_app(monkeypatch, "/akm")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/index.html")

    assert resp.status_code == 200
    assert resp.text.count("<base href=") == 1
    assert resp.text.count("window.__AKM_BASE__") == 1


# ---------------------------------------------------------------- MCP SSE


def _openapi_paths(app) -> dict:
    """取真实注册的路由路径.

    顶层 `app.routes` 里的 API 路由被包在惰性的 `_IncludedRouter` 里(FastAPI
    0.141),直接遍历拿不到嵌套路由,故用 OpenAPI schema。schema 里的路径**不含**
    部署前缀 —— 前缀由 FastAPI 写进 `servers`,不影响此处的比对。
    """
    return app.openapi()["paths"]


def test_mcp_messages_path_matches_actual_route(static_dir, monkeypatch):
    """SSE 通告的消息端点必须命中真实路由(否则客户端按通告地址回发必然 404).

    历史缺陷:`SseServerTransport("/messages")` 通告 `/messages`,而真实路由是
    `/api/mcp/messages` —— 实测 POST /messages → 404、POST /api/mcp/messages → 202。
    """
    app = make_app(monkeypatch, "")
    paths = _openapi_paths(app)

    assert MESSAGES_PATH in paths, (
        f"SSE 通告端点 {MESSAGES_PATH} 不是真实路由;现有路径:{sorted(paths)}"
    )
    assert "post" in paths[MESSAGES_PATH]


def test_sse_transport_wired_with_messages_path():
    """传输实例必须用该常量构造(防止再被改回 "/messages")."""
    from app.api.mcp import sse_transport

    assert sse_transport._endpoint == MESSAGES_PATH


@pytest.mark.parametrize(
    ("root_path", "advertised"),
    [("", "/api/mcp/messages"), ("/akm", "/akm/api/mcp/messages"), ("/a/b/c", "/a/b/c/api/mcp/messages")],
)
def test_sse_advertised_path_follows_root_path(root_path, advertised):
    """通告地址 = `scope['root_path'].rstrip('/') + 应用内路径`(mcp 库的拼法).

    因此常量只写应用内路径即可,子路径部署下客户端会自动收到带前缀的地址。
    """
    from app.api.mcp import sse_transport

    assert root_path.rstrip("/") + sse_transport._endpoint == advertised


def test_mcp_messages_path_is_absolute_without_prefix():
    """常量只写应用内路径,部署前缀由 mcp 库用 scope['root_path'] 拼上."""
    assert MESSAGES_PATH == "/api/mcp/messages"
