"""AgentKnowledgeMesh Node 客户端入口.

运行方式:
    uv run akm-node
    或
    python -m app
"""

import asyncio
import sys

from app.config import settings
from app.runner import HubClient

# Windows 兼容：当 stdout 被重定向（管道/后台服务/CI）且系统编码为 GBK 时，
# 下面的 emoji 状态打印会触发 UnicodeEncodeError，导致 Node 无法启动。
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    """启动 Node 客户端."""
    print("=" * 50)
    print("🔐 AgentKnowledgeMesh Node v0.2.0")
    print("=" * 50)
    print(f"📡 Hub URL: {settings.hub_url}")
    print(f"💻 Node: {settings.get_node_name()} ({settings.get_platform()})")
    print(f"📁 Knowledge: {', '.join(str(p) for p in settings.knowledge_paths) or 'Not configured'}")
    print("=" * 50)

    client = HubClient()

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n👋 Node stopped")


if __name__ == "__main__":
    main()
