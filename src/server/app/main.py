"""AgentKnowledgeMesh Server 应用入口.

启动方式:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    或
    python -m app
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import BASE_DIR, settings
from app.db import close_db, init_db
from app.services.websocket import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时初始化数据库
    await init_db()

    # 初始化向量数据库表（失败不阻塞启动，RAG 功能降级可用）
    try:
        from app.services.rag.vector_store import init_table

        init_table()
        print("✅ Vector DB (pgvector) initialized")
    except Exception as e:
        print(f"⚠️  Vector DB init failed: {e}")

    print(f"✅ AgentKnowledgeMesh v{settings.app_version} started")
    print(f"📁 Knowledge roots: {', '.join(str(p) for p in settings.knowledge_paths)}")
    print(f"💾 Database: {settings.db_path}")
    yield
    # 关闭时清理资源
    await close_db()
    print("👋 AgentKnowledgeMesh stopped")


def create_app() -> FastAPI:
    """创建 FastAPI 应用."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS 配置（开发环境允许前端跨域）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """SPA 路由：所有非 API 路径返回 index.html."""
            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(static_dir / "index.html"))

    return app


app = create_app()
