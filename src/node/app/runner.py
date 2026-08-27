"""Node 运行编排.

负责：
1. 连接 Hub
2. 编排心跳与消息处理
3. 断线重连
"""

import asyncio

from app.config import settings
from app.sync import DocumentSync
from app.transport import HubTransport


class HubClient:
    """Hub 客户端编排."""

    def __init__(self):
        self.transport = HubTransport(settings)
        self.sync = DocumentSync(self.transport, settings)

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
            await asyncio.sleep(settings.heartbeat_interval)
