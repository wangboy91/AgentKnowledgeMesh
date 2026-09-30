# node-env-login · 任务清单

## 1. 配置项

- [x] 1.1 `src/node/app/config.py` 新增 `hub_username` / `hub_password`(`AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD`)与 `has_hub_credentials` 判定(两者均非空);验证:`test_config.py` 补 `test_hub_credentials_absent_by_default`(默认空 → False)、`test_hub_credentials_require_both`(只填一个 → False,补齐 → True)、`test_hub_credentials_from_env_file`(.env 文件解析)→ 28 passed
- [x] 1.2 `src/node/.env.example` 增「Hub 账号(可选,用于免交互启动)」段,说明用途、明文密码风险与"首次自动登录后可移除"

## 2. 自动登录

- [x] 2.1 `src/node/app/login.py` 新增非交互 `auto_login(config) -> NodeSettings`:校验账号齐全 → 换取凭证(`_exchange_credentials` 新增 `config` 入参,`platform` / `node_id` 取传入配置而非模块单例)→ 尽力写回 `USER_ENV_FILE` 的 `AKM_NODE_ID` / `AKM_NODE_TOKEN`(写失败仅告警)→ 返回注入凭证的新配置;验证:`test_auto_login_swaps_credentials_and_persists`(换取入参、写回内容、原配置不被就地修改)、`test_auto_login_requires_account`、`test_auto_login_tolerates_env_write_failure` → 全绿
- [x] 2.2 `src/node/app/__main__.py` 提取启动前凭证解析 `_resolve_settings()`:有 token 直接用;无 token + 账号齐全 → `auto_login` 并同步模块级单例凭证(供 `--mcp` 读取);两者皆无 → 提示 + 退出码 1。分支位置在 `--help` / `--version` / `login` 之后、`--mcp` 与默认运行之前;验证:`test_env_account_auto_login_then_run`、`test_existing_token_skips_auto_login`、`test_no_token_and_no_account_exits_with_hint`、`test_auto_login_failure_exits_nonzero` → 全绿
- [x] 2.3 `--help` 文案补充环境变量自动登录说明;验证:`test_help_lists_commands_and_run_control` 增断言 `AKM_HUB_USERNAME` → 通过;实机 `python -m app --help` 输出含「无人值守部署可改配 AKM_HUB_USERNAME / AKM_HUB_PASSWORD」

## 3. 回归与验收

- [x] 3.1 凭证失效重登语义**不变**(本次刻意不引入静默重登,理由见 design D4);验证:`test_try_relogin_skipped_in_non_interactive_env` 保持通过,新增 `test_try_relogin_ignores_env_account`(配了账号也不触发 `auto_login` / `prompt_and_exchange`)→ 通过
- [x] 3.2 节点单测全量:`src/node` **129 passed**(基线 118,新增 11)
- [x] 3.3 服务端单测全量:`src/server` **188 passed**(未改动 server,零回归)
- [x] 3.4 端到端实测(隔离 Hub :8899 SQLite + 隔离 Node,脚本 `.workbuddy-ai/tmp/e2e-envlogin-drive.sh`):
  - 无凭证 + 只配 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` → 日志 `🔐 已用配置的 Hub 账号自动登录:node_id=4ddba99c…` → `✅ Registered with Hub` → `Synced 1 documents: created=1`;Hub 侧节点 `online`、`hello-envlogin.md` 归属该 node_id
  - 凭证写回 `auto.env`(`AKM_NODE_ID` + `AKM_NODE_TOKEN`)→ 与 Hub 侧 node_id 一致
  - 第二次启动(仍配着账号)→ 日志无「自动登录」、token 未轮换、`0 full-text, 1 hash-only`(走 token 路径)
  - 无凭证且未配账号 → `❌ 节点尚未接入…AKM_HUB_USERNAME / AKM_HUB_PASSWORD` + 退出码 1
  - 密码错误 → `❌ 自动登录失败:登录失败(401):用户名或密码错误` + 退出码 1
  - 收尾:端口 8899 已释放,无遗留进程
- [x] 3.5 文档同步:`README.md`(功能列表 / 节点接入 / 配置表 / 使用说明)、`docs/deployment.md` §2.2(免交互接入)/ §2.4(容器可省 login 一步)/ FAQ、`deploy/.env.example` §8、`deploy/docker-compose.node.yml`(变量透传 + 头部说明,`docker compose config` 通过)、两个安装脚本提示行;`docs/technical-design.md` 标注为冻结设计沿革,不改
