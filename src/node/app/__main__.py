"""AgentKnowledgeMesh Node 客户端入口.

运行方式:
    akm-node            (uv tool 安装的全局命令)
    uv run akm-node     (开发仓内)
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


def _get_version() -> str:
    """取包版本:安装版读包元数据,开发仓回退 dev 标记."""
    try:
        from importlib.metadata import version

        return version("akm-node")
    except Exception:
        return "0.2.0-dev"


def main():
    """启动 Node 客户端."""
    # 版本查询:akm-node --version / -V
    if "--version" in sys.argv or "-V" in sys.argv:
        print(_get_version())
        return

    # 登录子命令(account-auth):akm-node login
    if "login" in sys.argv:
        from app.login import run_login

        sys.exit(run_login())

    # 无凭证时拒绝启动(不再支持匿名接入)
    if not settings.node_token:
        print("❌ 节点尚未接入:请先执行 `akm-node login` 完成登录(account-auth)")
        sys.exit(1)

    # 本地 MCP 代理模式:智能体拉起子进程,stdio 提供与 Hub 同名的三个工具;
    # 单职责短生命周期进程,不启动同步循环
    if "--mcp" in sys.argv:
        from app.mcp_proxy import run_mcp_proxy

        asyncio.run(run_mcp_proxy())
        return

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
