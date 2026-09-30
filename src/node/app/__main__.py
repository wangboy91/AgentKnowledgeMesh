"""AgentKnowledgeMesh Node 客户端入口.

运行方式:
    akm-node            (uv tool 安装的全局命令)
    uv run akm-node     (开发仓内)
    或
    python -m app
"""

import asyncio
import sys

from app.config import NodeSettings, settings
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


def _print_help() -> None:
    """打印命令帮助(--help / -h)."""
    print(f"AgentKnowledgeMesh Node v{_get_version()}")
    print()
    print("用法:")
    print("  akm-node            连接 Hub 并常驻运行:扫描本地知识目录并同步")
    print("  akm-node login      登录接入:输入 Hub 地址与管理员账号,")
    print("                      成功后自动连接 Hub 并执行首次扫描同步")
    print("  akm-node --mcp      本地 MCP 代理模式(供本机智能体调用的检索工具)")
    print("  akm-node --version  显示版本")
    print("  akm-node --help     显示本帮助")
    print()
    print("运行控制:")
    print("  断开连接:Ctrl+C 退出进程")
    print("  断线重连:自动,连接断开后每 5 秒重试,Hub 恢复后自动接上并重新同步")
    print()
    print("凭证:")
    print("  交互登录一次即可,凭证保存在用户目录 .akm-node/.env")
    print("  (可用 AKM_NODE_ENV_FILE 自定义路径)")
    print("  无人值守部署可改配 AKM_HUB_USERNAME / AKM_HUB_PASSWORD 环境变量,")
    print("  启动时自动登录换取凭证(已有凭证时不再登录)")


def _print_banner(config: NodeSettings) -> None:
    """打印启动信息(默认运行与登录衔接共用)."""
    print("=" * 50)
    print(f"🔐 AgentKnowledgeMesh Node v{_get_version()}")
    print("=" * 50)
    print(f"📡 Hub URL: {config.hub_url}")
    print(f"💻 Node: {config.get_node_name()} ({config.get_platform()})")
    print(f"📁 Knowledge: {', '.join(str(p) for p in config.knowledge_paths) or 'Not configured'}")
    print("=" * 50)


def _run_client(client: HubClient) -> None:
    """前台运行客户端,统一 KeyboardInterrupt 处理."""
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n👋 Node stopped")


def _resolve_settings() -> NodeSettings:
    """启动前解析可用凭证配置(node-env-login).

    1. 已有节点凭证 → 直接用(不触发登录,避免每次启动轮换 token)
    2. 无凭证但配置了 Hub 账号 → 非交互自动登录换取凭证
    3. 两者都没有 → 提示先 login,以退出码 1 结束

    自动登录成功后,凭证同时同步回模块级 settings 单例:`--mcp` 等模块直接
    读取该单例,不同步会让它们拿到空凭证。
    """
    if settings.node_token:
        return settings

    if not settings.has_hub_credentials:
        print("❌ 节点尚未接入:请先执行 `akm-node login` 完成登录(account-auth)")
        print("   或在配置中提供 AKM_HUB_USERNAME / AKM_HUB_PASSWORD 以启动时自动登录")
        sys.exit(1)

    from app.login import auto_login

    try:
        fresh = auto_login(settings)
    except Exception as e:  # 网络错误、账号密码错误等
        print(f"❌ 自动登录失败:{e}")
        sys.exit(1)

    settings.node_id, settings.node_token = fresh.node_id, fresh.node_token
    return fresh


def main():
    """启动 Node 客户端."""
    # 帮助:akm-node --help / -h(短路,携带其他参数时同样只输出帮助)
    if "--help" in sys.argv or "-h" in sys.argv:
        _print_help()
        return

    # 版本查询:akm-node --version / -V
    if "--version" in sys.argv or "-V" in sys.argv:
        print(_get_version())
        return

    # 登录子命令(account-auth):换取凭证成功后自动进入运行循环
    # (连接 → 注册 → 首次扫描同步),不再以退出结束登录流程
    if "login" in sys.argv:
        from app.login import run_login

        if run_login() != 0:
            sys.exit(1)

        # 凭证刚写入 USER_ENV_FILE,模块级 settings 单例仍是旧值,
        # 须以新实例构造客户端(与 runner._try_relogin 的重载手法一致)
        fresh = NodeSettings()
        _print_banner(fresh)
        _run_client(HubClient(fresh))
        return

    # 凭证解析(无凭证且配置了 Hub 账号时自动登录;均不可用时退出)
    config = _resolve_settings()

    # 本地 MCP 代理模式:智能体拉起子进程,stdio 提供与 Hub 同名的五个工具;
    # 单职责短生命周期进程,不启动同步循环
    if "--mcp" in sys.argv:
        from app.mcp_proxy import run_mcp_proxy

        asyncio.run(run_mcp_proxy())
        return

    _print_banner(config)

    _run_client(HubClient(config))


if __name__ == "__main__":
    main()
