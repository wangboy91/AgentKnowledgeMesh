"""AgentVault Server 入口.

启动方式:
    python main.py
    或
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from db import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时初始化数据库
    await init_db()
    print(f"✅ AgentVault v{settings.app_version} started")
    print(f"📁 Knowledge roots: {', '.join(str(p) for p in settings.knowledge_paths)}")
    print(f"💾 Database: {settings.db_path}")
    yield
    # 关闭时清理资源
    await close_db()
    print("👋 AgentVault stopped")


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

# 注册路由
from api.router import router  # noqa: E402
app.include_router(router, prefix="/api")

# WebSocket 端点
from services.websocket import websocket_endpoint  # noqa: E402
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
import os
from pathlib import Path

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 路由：所有非 API 路径返回 index.html."""
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(static_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
