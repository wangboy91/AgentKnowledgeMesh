"""AgentKnowledgeMesh Node 客户端入口.

运行方式:
    python main.py
    或
    AV_HUB_URL=ws://hub:8000/ws AV_KNOWLEDGE_ROOTS=~/Knowledge python main.py
"""

import asyncio
from config import settings
from hub_client import HubClient


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
