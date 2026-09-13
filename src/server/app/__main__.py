"""python -m app 入口.

用法:
    python -m app           # Web 服务模式
    python -m app --mcp     # MCP Server stdio 模式
"""

import sys


def main():
    # 本机恢复命令:akm-hub reset-password <username>
    if len(sys.argv) > 1 and sys.argv[1] == "reset-password":
        import asyncio
        import getpass

        from app.services.auth import reset_password_cli

        def _read_password(prompt: str) -> str:
            # Windows 下 getpass 直读控制台,stdin 重定向(脚本/CI)时会永久阻塞,
            # 非 tty 环境回退普通读取
            if sys.stdin.isatty() and sys.stderr.isatty():
                return getpass.getpass(prompt)
            print(prompt, end="", flush=True)
            return sys.stdin.readline().rstrip("\r\n")

        username = sys.argv[2] if len(sys.argv) > 2 else input("用户名: ").strip()
        password = _read_password("新密码: ")
        confirm = _read_password("确认新密码: ")
        if password != confirm:
            print("❌ 两次输入不一致")
            sys.exit(1)
        if not password:
            print("❌ 密码不能为空")
            sys.exit(1)

        async def _reset():
            from app.db import init_db

            await init_db()
            return await reset_password_cli(username, password)

        ok = asyncio.run(_reset())
        print(f"✅ 已重置 {username} 的密码" if ok else f"❌ 用户 {username} 不存在")
        sys.exit(0 if ok else 1)

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
