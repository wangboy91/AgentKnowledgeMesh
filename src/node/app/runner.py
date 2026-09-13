"""Node 运行编排.

负责：
1. 连接 Hub
2. 编排心跳与消息处理
3. 断线重连
4. 凭证失效时现场重登(交互终端)
"""

import asyncio
import sys

from app.config import NodeSettings, settings
from app.sync import DocumentSync
from app.transport import HubTransport


class HubClient:
    """Hub 客户端编排."""

    def __init__(self):
        self.transport = HubTransport(settings)
        self.sync = DocumentSync(self.transport, settings)

    def _try_relogin(self) -> bool:
        """凭证失效时,在交互终端下现场重登并重建组件.

        非交互环境(脚本/服务)返回 False,保持重试循环。
        """
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return False
        try:
            answer = input("节点凭证已失效,是否现在重新登录?(Y/n): ").strip().lower()
        except (EOFError, OSError):
            return False
        if answer and answer not in ("y", "yes"):
            return False

        from app.login import prompt_and_exchange

        try:
            prompt_and_exchange(self.transport.settings.hub_api_url)
        except Exception as e:
            print(f"❌ 重新登录失败:{e}")
            return False

        # 重新读取 .env,重建传输与同步组件
        fresh = NodeSettings()
        self.transport = HubTransport(fresh)
        self.sync = DocumentSync(self.transport, fresh)
        print("✅ 已获取新凭证,正在重连…")
        return True

    async def run(self):
        """运行客户端主循环."""
        while True:
            try:
                if await self.transport.connect():
                    # 启动心跳任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    # 启动消息处理
                    message_task = asyncio.create_task(self.transport.handle_messages(self.sync))

                    # 初始同步
                    await self.sync.sync_documents()

                    # 等待任一任务完成
                    done, pending = await asyncio.wait(
                        [heartbeat_task, message_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 取消剩余任务
                    for task in pending:
                        task.cancel()
                elif self.transport.credential_failed and self._try_relogin():
                    # 现场重登成功,立即用新凭证重连
                    continue

                # 断线重连
                print("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n👋 Shutting down...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(5)

    async def _heartbeat_loop(self):
        """心跳循环."""
        while self.transport.connected:
            await self.transport.send_heartbeat()
            await asyncio.sleep(self.transport.settings.heartbeat_interval)
