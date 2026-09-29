"""Node 运行编排.

负责：
1. 连接 Hub
2. 编排心跳与消息处理
3. 断线重连
4. 凭证失效时现场重登(交互终端)
5. 文件变更监听与定时对账(add-node-file-watch)

触发模型：监听负责实时(低延迟)，定时对账负责最终一致(兜住监听丢事件的
场景)，两者与既有的"启动 / 重连 / Hub sync_request"共同汇入
`DocumentSync.sync_documents()`。
"""

import asyncio
import sys
from pathlib import Path

from watchfiles import Change, awatch

from akm_shared.scanner import is_watchable_markdown

from app.config import NodeSettings
from app.config import settings as default_settings
from app.sync import DocumentSync
from app.transport import HubTransport

# 写入稳定性检查的两次 stat 间隔（秒）；监听异常退避的上限（秒）
STABILITY_CHECK_INTERVAL = 0.3
WATCH_MAX_BACKOFF = 60


def _make_watch_filter(roots: list[Path], extra_excluded: set[str]):
    """构造 watchfiles 的过滤回调.

    与扫描器共用 `is_watchable_markdown`，保证"监听得到的"与"扫描得到的"
    一致——两处语义漂移会让文档在下一轮全量对账中被误判为删除。
    """

    def _filter(change: Change, raw_path: str) -> bool:
        path = Path(raw_path)
        return any(
            is_watchable_markdown(path, root, extra_excluded=extra_excluded)
            for root in roots
        )

    return _filter


def _split_changes(changes) -> tuple[list[Path], list[Path]]:
    """把 watchfiles 的变更集合拆成 (changed, deleted) 绝对路径列表.

    删除事件必须单独收集——局部同步只认显式删除，绝不从"未扫描到"推导
    (见 DocumentSync.sync_paths)。
    """
    changed: list[Path] = []
    deleted: list[Path] = []
    for change, raw_path in changes:
        path = Path(raw_path)
        if change == Change.deleted:
            deleted.append(path)
        else:
            changed.append(path)
    # 同一路径可能同时出现在 added/modified 中，去重且保持顺序
    return list(dict.fromkeys(changed)), list(dict.fromkeys(deleted))


class HubClient:
    """Hub 客户端编排."""

    def __init__(self, settings: NodeSettings | None = None):
        # 配置可注入:login 成功衔接时凭证刚写入 .env,模块级单例仍是旧值,
        # 须以新 NodeSettings 实例构造(与 _try_relogin 的重建手法一致)
        if settings is None:
            settings = default_settings
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
                    # 文件监听与定时对账：**不参与下方 FIRST_COMPLETED 竞争**——
                    # 它们若参与，心跳正常结束也会被当成断线触发重连
                    watch_task = asyncio.create_task(self._watch_loop())
                    reconcile_task = asyncio.create_task(self._reconcile_loop())

                    # 初始同步
                    await self.sync.sync_documents()

                    # 等待任一任务完成
                    done, pending = await asyncio.wait(
                        [heartbeat_task, message_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 取消剩余任务（含监听与对账，避免重连后叠加多组循环）
                    for task in (*pending, watch_task, reconcile_task):
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

    async def _watch_loop(self):
        """文件变更监听循环(add-node-file-watch).

        异常一律内部消化并退避重试：监听失效不应拖垮心跳与消息链路。本循环
        **不参与** run() 的 FIRST_COMPLETED 竞争，仅由断线/退出时的 cancel 收掉。
        """
        settings = self.transport.settings
        if not settings.watch_enabled:
            print("👁 文件监听已关闭(AKM_WATCH_ENABLED=false),依赖定时对账")
            return

        extra_excluded = settings.watch_excluded_names
        backoff = 5
        while True:
            roots = settings.knowledge_paths
            if not roots:
                # 无知识根可监听：空转等待，不退出（目录可能稍后创建）
                print("👁 无可监听的知识库目录,60 秒后重试")
                await asyncio.sleep(60)
                continue
            try:
                print(
                    f"👁 监听中: {', '.join(str(r) for r in roots)} "
                    f"(防抖 {settings.watch_debounce_seconds:g}s)"
                )
                async for changes in awatch(
                    *[str(root) for root in roots],
                    watch_filter=_make_watch_filter(roots, extra_excluded),
                    debounce=int(settings.watch_debounce_seconds * 1000),
                ):
                    backoff = 5
                    changed, deleted = _split_changes(changes)
                    # 写入稳定性检查（并发进行，总耗时约等于单次检查）
                    if changed:
                        stable = await asyncio.gather(
                            *(self._is_stable(path) for path in changed)
                        )
                        changed = [p for p, ok in zip(changed, stable) if ok]
                    if changed or deleted:
                        await self.sync.sync_paths(changed=changed, deleted=deleted)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ 文件监听异常: {e};{backoff} 秒后重试")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, WATCH_MAX_BACKOFF)

    @staticmethod
    async def _is_stable(path: Path) -> bool:
        """写入稳定性检查：间隔 STABILITY_CHECK_INTERVAL 的两次 stat 是否一致.

        防抖只保证事件聚合，不保证文件写完（大文件复制场景）；不稳定则跳过该
        文件、不阻塞同轮其他文件，由定时对账兜底。
        """
        try:
            first = path.stat()
        except OSError:
            return False
        await asyncio.sleep(STABILITY_CHECK_INTERVAL)
        try:
            second = path.stat()
        except OSError:
            return False
        return (first.st_size, first.st_mtime_ns) == (
            second.st_size,
            second.st_mtime_ns,
        )

    async def _reconcile_loop(self):
        """定时全量对账(add-node-file-watch)：兜住监听丢事件的场景.

        跨平台事件差异、缓冲区溢出、网络文件系统都可能丢事件；对账保证最终
        一致。间隔为 0 时不启动。
        """
        settings = self.transport.settings
        interval = settings.watch_reconcile_seconds
        if interval <= 0:
            print("🧭 定时对账已关闭(AKM_WATCH_RECONCILE_SECONDS=0),仅依赖监听")
            return

        print(f"🧭 定时对账:每 {interval} 秒全量扫描一次")
        while True:
            await asyncio.sleep(interval)
            try:
                await self.sync.sync_documents()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # 对账失败不影响下一轮；快照未动，下轮自然重试
                print(f"⚠️ 定时对账失败: {e}")
