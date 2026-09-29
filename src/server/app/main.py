"""AgentKnowledgeMesh Server 应用入口.

启动方式:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    或
    python -m app
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.gzip import GZipMiddleware

from app.api import router
from app.config import BASE_DIR, settings
from app.db import close_db, init_db
from app.services.websocket import websocket_endpoint

# Windows 兼容：当 stdout 被重定向（管道/后台服务/CI）且系统编码为 GBK 时，
# 下面的 emoji 状态打印会触发 UnicodeEncodeError，导致应用启动失败。
# 统一把输出流重配置为 UTF-8；MCP stdio 模式不经过本模块，不受影响。
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时初始化数据库
    await init_db()

    # 首次启动创建管理员账号(account-auth)
    from app.services.auth import ensure_admin_user

    await ensure_admin_user()

    # 启动时无任何活跃连接,重置残留的"在线"节点状态
    from app.services.websocket import reset_all_nodes_offline

    await reset_all_nodes_offline()

    # 向量化总开关(默认关闭):关闭时跳过向量库初始化,不产生任何嵌入调用;
    # 语义检索端点降级为关键词检索(见 api/rag.py)
    from app.db import async_session
    from app.services.rag.sync import get_vectorization_enabled

    async with async_session() as session:
        vectorization_enabled = await get_vectorization_enabled(session)

    if vectorization_enabled:
        # 初始化向量数据库表（失败不阻塞启动，RAG 功能降级可用）
        try:
            from app.services.rag.vector_store import init_table

            init_table()
            print("✅ Vector DB (pgvector) initialized")
        except Exception as e:
            print(f"⚠️  Vector DB init failed: {e}")
    else:
        print("ℹ️  Vectorization disabled (vector DB not initialized); enable it in Settings")

    print(f"✅ AgentKnowledgeMesh v{settings.app_version} started")
    print(f"📁 Knowledge roots: {', '.join(str(p) for p in settings.knowledge_paths)}")
    print(f"💾 Database: {settings.db_type} -> {settings.db_host}:{settings.db_port}/{settings.db_name}"
          if settings.db_type == "postgres"
          else f"💾 Database: {settings.db_path}")
    if settings.root_path:
        print(f"🔗 Deploy root path: {settings.root_path} (经反向代理子路径访问)")
    else:
        print("🔗 Deploy root path: / (域名根路径)")
    yield
    # 关闭时清理资源
    await close_db()
    print("👋 AgentKnowledgeMesh stopped")


def render_index_html(index_path: Path, root_path: str) -> str:
    """把部署前缀注入 index.html(文档基址 + 运行时基址).

    - `<base href>`:让构建产物里的相对资源引用(`./assets/*`)解析到部署前缀下
    - `window.__AKM_BASE__`:给前端路由 basename 与 API 基址
      (react-router 的 basename 不读 `document.baseURI`,故必须显式给出)

    因此同一份前端构建产物可在任意深度的子路径下运行,无需为每个前缀重新构建。
    根路径部署时两者均为 `/`,与不注入时等价。
    """
    html = index_path.read_text(encoding="utf-8")
    base = f"{root_path}/" if root_path else "/"
    injected = (
        f'\n    <base href="{base}" />'
        f'\n    <script>window.__AKM_BASE__ = "{base}";</script>'
    )
    return html.replace("<head>", f"<head>{injected}", 1)


def resolve_static_file(static_root: Path, full_path: str) -> Path | None:
    """把请求路径解析成 static/ 下的真实文件;越界或不存在返回 None.

    刻意不用 `app.mount("/assets", StaticFiles(...))`:Mount 会把挂载点追加进
    `scope["root_path"]`(见 starlette `Mount.matches`),而 `StaticFiles` 内部
    又用 `get_route_path` 去掉该前缀 —— 于是代理**剥离**前缀时(应用收到
    `/assets/x.js`,而子 scope 的 root_path 已是 `/akm/assets`)会解析成
    `static/assets/assets/x.js`,必然 404。统一由 catch-all 兜底后,
    「代理剥离前缀」与「代理保留前缀」两种反代写法得到一致结果(subpath-deployment)。
    """
    if not full_path or full_path == "index.html":
        return None
    candidate = (static_root / full_path).resolve()
    # 防目录穿越:`/../app/config.py` 之类不得逃出 static/
    if not candidate.is_relative_to(static_root):
        return None
    return candidate if candidate.is_file() else None


def create_app() -> FastAPI:
    """创建 FastAPI 应用."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        # 部署前缀(subpath-deployment):FastAPI 会把它写入 scope["root_path"],
        # 供 OpenAPI servers / url_for / MCP SSE 通告地址使用;Starlette 路由匹配
        # 会按需剥掉它,因此「代理剥离前缀」与「代理保留前缀」两种反代写法都能命中。
        root_path=settings.root_path,
    )

    # CORS 配置（开发环境允许前端跨域）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 响应压缩(大 JSON 树/文档体积显著下降;SSE/MCP 长连接由 starlette
    # 对 text/event-stream 跳过压缩,不受影响)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # API 路由
    app.include_router(router, prefix="/api")

    # WebSocket 端点
    app.add_api_websocket_route("/ws", websocket_endpoint)

    @app.get("/api/health")
    async def health():
        """健康检查."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
        }

    # 静态文件服务（生产模式：前端构建产物）
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        static_root = static_dir.resolve()

        index_path = static_dir / "index.html"
        # 启动时渲染一次并缓存(root_path 进程内固定);index.html 缺失时保持原行为
        index_html = (
            render_index_html(index_path, settings.root_path) if index_path.is_file() else None
        )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """SPA 路由:静态目录中的真实文件原样返回,其余回退 index.html.

            回退的 index.html 已注入部署前缀(subpath-deployment),并显式禁用缓存
            —— 它是资源清单的入口,缓存住会导致发版后仍加载旧哈希资源。
            """
            file_path = resolve_static_file(static_root, full_path)
            if file_path is not None:
                return FileResponse(str(file_path))
            if index_html is not None:
                return HTMLResponse(index_html, headers={"Cache-Control": "no-cache"})
            return FileResponse(str(index_path))

    return app


app = create_app()
