# login-auto-run · 任务清单

## 1. CLI 帮助入口

- [x] 1.1 在 `src/node/app/__main__.py` 增加 `--help` / `-h` 短路分支(优先级在 login 判定之前),输出命令列表(`login` / 默认运行 / `--mcp` / `--version`)、断开方式(Ctrl+C)与断线自动重连(5 秒)说明,退出码 0;验证:`uv run akm-node --help` 与 `-h` 输出含关键行且不启动客户端 → 实测退出码 0、输出含 `login` / `--mcp` / `--version` / `Ctrl+C` / `5 秒`,未发起连接
- [x] 1.2 在 `src/node/tests` 补帮助输出测试(断言关键命令行与重连说明存在、`--help` 不触发连接),验证:`uv run pytest src/node/tests -k help` 通过 → `test_help_lists_commands_and_run_control` / `test_help_short_flag_and_priority`(含 `-h login` 并存时仅输出帮助)

## 2. 登录后自动接入

- [x] 2.1 调整 `run_login()`(src/node/app/login.py)返回成功标志并更新成功提示文案(说明即将自动接入、Ctrl+C 退出),失败路径保持非零退出;验证:单测覆盖成功/失败返回值 → `test_run_login_success_returns_zero_with_auto_run_hint` / `test_run_login_failure_returns_nonzero`
- [x] 2.2 在 `__main__.py` login 分支实现衔接:`run_login()` 成功后重载配置(拿到新写入的凭证,D2)并 `asyncio.run(HubClient().run())`,KeyboardInterrupt 处理与默认运行入口一致;验证:本地对 Hub 实测 `uv run akm-node login` 一条命令完成登录 → 连接 → 首次扫描同步(Hub 日志出现 `Node connected` 且文档上传 200) → 临时 Hub(SQLite,:8124)实测:登录成功 → banner(Hub URL/节点/知识目录) → `Registered with Hub` → `Found 1 documents` → `PUT /nodes/{id}/documents` 200,Hub 侧文档含 `hello-e2e.md`;进程登录后保持运行
- [x] 2.3 补衔接测试:登录写入新 `.env` 后 `HubClient` 构造时读到新 `AKM_NODE_TOKEN`(防模块级 settings 单例持旧值回归),验证:`uv run pytest src/node/tests` 全量通过 → `test_hubclient_uses_fresh_settings`(新 token/URL 生效)、`test_login_success_enters_run_loop_with_fresh_credentials`(login 分支以新 settings 进入 `run()`)、`test_login_failure_exits_nonzero_without_run`(失败退出码 1 且不启动客户端);全量 53 passed

## 3. 回归与验收

- [x] 3.1 回归既有 CLI 语义:`--version`、`--mcp`、无凭证启动报错退出码 1、凭证失效现场重登(`_try_relogin`)均不受影响;验证:`uv run pytest src/node/tests` 全量通过 + 手动核对 `--version` / 无凭证提示 → 节点 53 passed;`uv run akm-node --version` 输出 `0.2.0`;空凭证启动输出「节点尚未接入」且退出码 1;服务端 112 passed;前端 `npm run build` 成功;`_try_relogin` 补回归测试(`test_try_relogin_rebuilds_components_with_new_credentials` / `test_try_relogin_skipped_in_non_interactive_env`),确认 `HubClient` 增加配置注入后重登路径仍以新凭证重建 transport/sync
- [ ] 3.2 双机联调验收:WANG-Work-PC 全新凭证执行 `uv run akm-node login`,确认一条命令后 Hub 侧节点在线且文档完成首次同步;Ctrl+C 断开后 Hub 侧节点转离线
  - 待用户实机执行(本地已用临时 Hub 覆盖"登录 → 在线 → 首次同步";本机以 SIGINT 模拟 Ctrl+C 在 Windows 下不触发控制台中断,断开→离线一项需实机确认)
