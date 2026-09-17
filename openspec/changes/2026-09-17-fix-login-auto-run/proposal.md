# login-auto-run

## Why

多节点实测暴露体验断点:`akm-node login` 是一次性命令,换取凭证写入 `.env` 后直接退出,用户必须再手动执行 `akm-node` 才会连接 Hub 并扫描上传。登录与运行之间的断裂造成"登录成功但 Hub 侧看不到节点在线、文件扫描不出来"的困惑(2026-09-17 WANG-WorkPC 接入实测复现)。同时 CLI 缺少 `--help`,断开/重连方式没有任何提示。

## What Changes

- `akm-node login` 成功换取凭证后**不再退出**,自动进入运行循环:连接 Hub → 注册 → 初始扫描同步 → 常驻(Ctrl+C 退出)
- 新增 `--help` / `-h` 输出:列出 `login` / 默认运行 / `--mcp` / `--version` 用法,并说明断开方式(Ctrl+C)与断线自动重连(5 秒间隔)行为
- 登录成功后的提示文案同步更新(从"之后直接运行 akm-node"改为"即将自动接入")

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `account-auth`: Requirement「节点凭证获取与生命周期」——`akm-node login` 成功后的行为从"写凭证后退出"变为"写凭证后自动接入 Hub 并执行初始同步";新增节点 CLI 帮助入口(`--help`)的要求

## Impact

- `src/node/app/__main__.py`:login 分支衔接运行循环;新增 `--help` 分支
- `src/node/app/login.py`:`run_login` 返回语义调整(成功后由调用方进入运行循环);提示文案
- `src/node/app/runner.py`:可能需要支持登录后以新凭证构造 `HubClient` 直接启动
- 无对外契约变更(WS / HTTP / MCP 协议均不变),Hub 端零改动,不影响已部署节点
- 服务端重启后的客户端自动重连**已存在**(runner 5 秒重连循环,`multi-node-sync` 已有「Node 自动重连」场景),本变更不改该机制,仅在帮助文本中向用户说明
