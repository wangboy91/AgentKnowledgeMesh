# login-auto-run · 设计

## Context

当前 CLI 入口(`src/node/app/__main__.py`):`login` 参数走 `run_login()` → 换凭证 → `sys.exit(0)`,进程结束;运行循环由 `HubClient.run()` 承担(连接 → 心跳/消息双任务 → 初始同步 → 断线 5 秒重连)。`runner._try_relogin` 中已存在"重登后重建组件再继续运行"的先例:登录与运行循环可以衔接,不需要新机制。

约束:
- 运行循环内再次构造 `NodeSettings` 读取的是登录刚写入的 `~/.akm-node/.env`(`_update_env` 原子写),衔接处无需传值
- `--mcp` 模式与 `--version` 必须保持短路语义,不受 `--help` 影响

## Goals / Non-Goals

**Goals:**
- `login` 成功后无缝进入 `HubClient.run()`,一次命令完成"登录 + 接入 + 首次同步"
- `--help` / `-h` 覆盖全部命令面,包含断开(Ctrl+C)与重连(5 秒)说明
- 登录失败仍以非零退出码结束,不进入运行循环

**Non-Goals:**
- 不改 Hub 端任何代码与协议(WS/HTTP/MCP 均不变)
- 不改既有断线重连机制(已满足"服务端重启后客户端自动重连")
- 不引入后台服务/守护进程模式(前台常驻即当前产品形态;`disconnect`/`reconnect` 独立子命令需要守护化,超出本次范围,帮助文本中以 Ctrl+C + 重新执行说明代替)
- 不做重连退避策略与负载优化(见 Risks 注记)

## Decisions

### D1: 衔接方式 —— login 成功后直接调用 `HubClient().run()`
`run_login()` 保持纯登录职责、返回成功标志;由 `__main__.py` 的 login 分支在成功后 `asyncio.run(client.run())`(复用现有运行入口的打印与 KeyboardInterrupt 处理)。
- 备选:在 `run_login` 内部直接 run——职责混杂,且凭证失效现场重登(`_try_relogin`)无法复用同一衔接路径
- 备选:登录后 `os.execv` 重启自身——Windows 上行为不稳,且丢失当前控制台状态

### D2: 凭证热加载 —— 衔接处重新实例化 `HubClient`
`login` 分支在 `run_login()` 返回成功后新建 `HubClient()`(其内部 `settings` 为模块级单例,需在衔接前重载配置)。
具体:将 `__main__.py` 中 `from app.config import settings` 的模块级导入改为运行时读取,或为 `NodeSettings` 提供 reload;实现时取改动最小者,保证 `HubClient` 拿到的是**新写入的凭证**而非进程启动时的旧值。
- 依据:`runner._try_relogin` 已验证"重读 .env → 重建组件"路径可行,本决策只是把同一手法用于进程内衔接

### D3: `--help` 实现为参数短路,优先级置于 login 判定之前
判定顺序:`--help/-h` → `--version/-V` → `login` → 无凭证拦截 → `--mcp` → 运行。帮助文本静态硬编码,不走 argparse(现有 CLI 是裸 `sys.argv` 判断风格,引入 argparse 属于无关重构)。

## Risks / Trade-offs

- [模块级 `settings` 单例在登录后持有旧凭证] → D2 的重载衔接;实现任务中包含一条针对性测试(登录写新 .env 后 HubClient 读到新 token)
- [login 成功即常驻,自动化脚本里登录后无法退出] → 帮助文本说明 Ctrl+C;脚本场景可用 `akm-node login < /dev/null` 之外的方式(登录本身是交互式的,自动化本就不适用,风险低)
- [断线固定 5 秒重连对 Hub 有持续压力,大规模节点下放大] → 当前规模(个位数节点)可接受,记录为已知负载特征;后期优化方向:指数退避 + 抖动,或改用服务端推送/消息队列架构。本变更不动
- [帮助文本与实际命令行为漂移] → 帮助内容纳入 tasks 的测试项(断言关键行存在),漂移时测试失败

## Migration Plan

纯客户端变更,节点包版本升级即生效;旧版节点(登录即退出)行为不变,无兼容性问题。回滚 = 回退节点包版本。

## Open Questions

(无)
