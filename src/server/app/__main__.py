"""python -m app 入口.

用法:
    python -m app           # Web 服务模式
    python -m app --mcp     # MCP Server stdio 模式
"""

import sys


def main():
    if "--mcp" in sys.argv:
        import asyncio

        from app.services.mcp_server import run_mcp_stdio

        asyncio.run(run_mcp_stdio())
    else:
        import uvicorn

        from app.config import settings

        uvicorn.run(
            "app.main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
        )


if __name__ == "__main__":
    main()
