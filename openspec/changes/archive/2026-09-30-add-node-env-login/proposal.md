# node-env-login

## Why

节点接入凭证目前只能由 `akm-node login` 交互输入换取,再落到 `~/.akm-node/.env`。这在两类场景下不便:

- **无人值守部署**(systemd / 计划任务 / 容器):首次接入必须有人在终端前敲账号密码;节点容器还要多一步 `run --rm ... login` 才能常驻,登录与运行被拆成两次启动。
- **凭证轮换**:Web 端重置 token 后,非交互环境下的节点只能每 5 秒重试并反复打印"凭证失效",必须人工再跑一次 `login`。

节点配置本就以环境变量为主入口(`AKM_HUB_URL` / `AKM_KNOWLEDGE_ROOTS` / `AKM_WATCH_*`),账号密码没有理由例外。

## What Changes

- 新增 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 两个配置项(进程环境变量或 `.env` 均可,优先级沿用现有解析顺序)
- **启动自动登录**:启动时若无节点凭证(`AKM_NODE_TOKEN` 为空)但账号密码均已配置,则非交互调用 `POST /api/auth/login` + `POST /api/nodes/register` 换取凭证,继续照常连接 Hub 并同步;凭证尽力写回用户级 `.env`(写失败只告警,本次运行使用内存凭证)
- **已有凭证时不重复登录**:`AKM_NODE_TOKEN` 非空时直接使用,不调用登录/注册端点(避免每次启动轮换 token)
- **未配置账号时行为不变**:无凭证启动仍提示 `akm-node login` 并以退出码 1 结束,提示文案补充环境变量选项
- `akm-node login` 交互登录入口**保持不变**,仍是首次接入的推荐方式;`--help` 文案补充新配置说明
- **非目标**:运行中凭证失效后的"静默自动重登"本次不做(Hub 的 `register` 会清除 `disabled`,静默重登会让 admin 的"禁用"失效;见 design D4)

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `account-auth`:**新增** Requirement「节点环境变量凭证与启动自动登录」(纯新增,不改动既有 Requirement 的文本与场景)

## Impact

- `src/node/app/config.py`:新增 `hub_username` / `hub_password` 配置项与 `has_hub_credentials` 判定
- `src/node/app/login.py`:新增非交互 `auto_login()`,与交互式 `prompt_and_exchange()` 共用换取逻辑
- `src/node/app/__main__.py`:启动前统一解析可用凭证(覆盖默认运行与 `--mcp` 两条路径);提示文案与 `--help`
- `src/node/tests/`:`test_config.py` / `test_cli.py` 补用例
- 文档:`src/node/.env.example`、`README.md`、`docs/deployment.md` §2.2 / §2.4 / FAQ、`deploy/.env.example` §8、`deploy/docker-compose.node.yml` 与两个安装脚本的提示行
- 不改 `docs/technical-design.md`:该文自 2026-09-17 起标注为设计沿革(「不再随实现演进更新」),本次不改其冻结内容
- **无对外契约变更**:复用既有 `POST /api/auth/login` 与 `POST /api/nodes/register`,Hub 端零改动,WS / HTTP / MCP 协议不变,不影响已部署节点与 Hub
- 安全提示:环境变量中的密码为明文,文档需说明"首次自动登录后凭证已落 `.env`,可移除密码"
