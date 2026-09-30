# node-env-login · 设计

## 背景

节点侧凭证链路现状(见 `docs/technical-design.md` §3):

```
akm-node login(交互: Hub API 地址 / 用户名 / 密码)
  → POST /api/auth/login(JWT)
  → POST /api/nodes/register(带 JWT + node_name/platform/node_id)
  → {node_id, node_token} 写入 ~/.akm-node/.env
  → 自动进入运行循环(WS register 携带 node_token)
```

配置解析优先级:`进程环境变量 > AKM_NODE_ENV_FILE(默认 ~/.akm-node/.env) > src/node/.env(仅开发仓)`。

## D1 · 配置项命名:`AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD`

这两个值是**登录 Hub 的账号**(不是节点自身标识),与既有 `AKM_HUB_URL` / `AKM_HUB_API_URL` 同族,归到 `.env.example` 的「Hub 连接」段最自然,也便于"要连哪个 Hub 就连哪套账号"的直觉。

字段名 `hub_username` / `hub_password`,判定属性 `has_hub_credentials`(两者均非空才算配置完整,只填一个视为未配置)。

> 不采用 `AKM_NODE_LOGIN_*`:与节点自身身份(`AKM_NODE_ID` / `AKM_NODE_NAME`)易混。

## D2 · 凭证优先级:`AKM_NODE_TOKEN` 优先,密码只在无凭证时使用

```
AKM_NODE_TOKEN 非空            → 直接用 token 连接(不调登录/注册)
AKM_NODE_TOKEN 为空 + 账号齐全 → 自动登录换取凭证 → 写回 .env → 用新凭证连接
两者都不满足                   → 提示先 login,退出码 1
```

理由:`POST /api/nodes/register` 每次调用都**轮换** node_token。若每次启动都拿密码换一遍,会持续轮换 token(虽无功能损害,但制造无谓的写库与日志噪音),也让"密码轮换后忘删"变成隐式风险。让 token 一旦落盘就成为稳态路径,密码退化为"首次接入 / 失效恢复"的引导手段。

## D3 · 自动登录写回 `.env`,失败不阻断

`auto_login()` 与交互登录写回**同一组键**(`AKM_NODE_ID` / `AKM_NODE_TOKEN`),位置同为 `USER_ENV_FILE`:

- 与 `akm-node login` 行为对齐,用户只需理解一套凭证存储;
- 首次自动登录成功后,密码即可从配置中移除,后续启动直接走 token;
- **不写** `AKM_HUB_API_URL` / `AKM_HUB_URL`:自动登录场景下这两个地址本来就来自配置(环境变量或 `.env`),回写是多余的,还可能把容器里由 compose 注入的地址固化到容器卷里,反而在下次换地址时造成困惑(容器场景进程环境变量优先级更高,固化值不会生效,但会误导排查)。

写文件用 `try/except OSError` 包住:只读挂载 / 权限不足时仅打印告警,本次运行使用内存中的凭证(返回值已注入),不因落盘失败而中断接入。

## D4 · 不做"凭证失效后静默重登"(非目标,已评估)

看起来很自然的一步——运行中 token 被重置时用配置的账号静默重登——**本次刻意不做**,原因是一个治理隐患:

- Hub 的 `POST /api/nodes/register` 会 `node.disabled = False`(重新登录 = 重新接入)
- 而 WS 注册失败时节点只能拿到统一的 `Invalid node credentials`,**无法区分**"token 失效"与"节点被禁用"
- 于是配置了账号的无人值守节点会在被 admin 禁用后,自动登录 → 重新注册 → 把禁用**悄悄解除**,每 5 秒一次

既有交互式重登也有同样效果,但那需要有人坐在终端前确认(等于人工重新接入);改成静默自动后,admin 的"禁用"将失去约束力。要做这件事的前提是先让"禁用"变粘性(register 不得清除 disabled,或节点在重登前先查节点状态),那是一次独立的、有兼容性影响的变更。

因此本变更只覆盖**启动时**的自动登录:此时若本地已有凭证(含被禁用的节点)则直接走 token 路径,不触发登录。

## D5 · 覆盖 `--mcp` 路径

`akm-node --mcp` 目前同样要求"已有凭证"(无 token 直接退出)。凭证解析提取为入口处统一的一步(`_resolve_settings()`),放在 `--help` / `--version` / `login` 三个短路分支之后、`--mcp` 与默认运行之前,两条路径共享同一套语义。

`--mcp` 的代理模块直接读取模块级 `settings` 单例,因此自动登录成功后除了用新实例构造 `HubClient`,还要把 `node_id` / `node_token` 同步回该单例,保证同一进程内所有读者看到同一凭证。

## 备选方案(未采用)

| 方案 | 否决理由 |
| --- | --- |
| 新增 `akm-node login --username/--password` 命令行参数 | 密码进 shell 历史与进程列表,泄露面更大;环境变量可由部署编排(compose / systemd 的 EnvironmentFile)安全管理 |
| 在 `config.py` 模块加载时自动登录 | 副作用藏在 import 里:任何 `import app.config`(含单测、`--help`)都会发网络请求 |
| 复用 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD`(Hub 侧同名变量) | 语义不同:Hub 侧是"初始化管理员",节点侧是"登录用账号";同名会让"节点机也配了这两个变量"变成隐性串号 |
| 自动登录后不再写 `.env`,只保留内存凭证 | 每次启动都轮换 token;进程重启即丢失,容器场景每次重启都要走完整登录,日志噪音大 |
