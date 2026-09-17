# 提案:打包发布 v0.2.0(Hub 容器镜像 + akm-node 一键安装)

## Why

AKM 目前只能在开发仓内以 `uv run` 方式运行,没有可分发的版本产物:Hub(server+web)虽有 Dockerfile 但缺少构建卫生(会把 `.venv`、含密钥的 `.env` 打进镜像)与发版通道;akm-node 依赖 path 依赖 `akm-shared` 且配置文件锚定在源码目录,无法在远程机器上一条命令安装。要让知识库真正跑到多台机器上(本产品的核心场景),必须先具备"Hub 一份容器镜像部署、任意机器一条命令装出 `akm-node`"的分发能力。

## What Changes

- **新增 `src/.dockerignore`**:排除 `.venv`、`node_modules`、`tests`、`data`、`.env` 等,保证镜像构建干净且不泄密(当前 `COPY server/ .` 会把 `server/.env` 连同数据库密码打进镜像)。
- **修正 `src/Dockerfile` 与 `src/Dockerfile.node`**:固定 uv 版本(不再用 `latest`);Hub 镜像统一命名 `ghcr.io/wangboy91/akm-hub`。
- **调整 akm-node 配置文件位置**:凭证 `.env` 从包目录(`BASE_DIR`)迁移到用户目录 `~/.akm-node/.env`(支持 `AKM_NODE_ENV_FILE` 环境变量覆盖);读取时兼容仓库内开发场景的 `src/node/.env`。**BREAKING**(仅对以 `uv tool install` 安装的用户,当前尚无此类用户,实际影响为零)。
- **新增发版流水线 `.github/workflows/release.yml`**:打 `v*` tag 触发 —— 构建 `akm-shared`/`akm-node` wheel、构建并推送 Hub 镜像到 GHCR、创建 GitHub Release(附 wheels + 安装脚本 + 部署用 compose 文件)。
- **新增一键安装脚本** `scripts/install-akm-node.sh`(bash)与 `scripts/install-akm-node.ps1`(PowerShell):检测/安装 uv → 从 GitHub Release 下载 wheels → `uv tool install akm-node --find-links` → 提示 `akm-node login`。
- **新增部署文档** `docs/deployment.md`:Hub 容器部署(GHCR 镜像 + compose,含管理员初始化与数据持久化)、akm-node 安装与接入、`akm-node --mcp` 接入本机智能体的配置示例。
- **开源协议采用 MIT**:根目录新增 `LICENSE`(MIT),`server`/`node`/`shared` 的 `pyproject.toml` 补 `license` 字段,README 增加协议说明。
- **版本统一为 0.2.0** 并以 `v0.2.0` tag 发布(由用户本人执行 commit/push/tag)。

## Capabilities

### New Capabilities

- `release-distribution`: 版本分发能力 —— Hub 以容器镜像(GHCR)分发部署;akm-node 以 GitHub Release wheel + 一键安装脚本分发,安装后在任意机器提供全局 `akm-node` 命令(login 接入 / 常驻同步 / `--mcp` 检索代理),凭证持久化于用户目录且升级不丢失。

### Modified Capabilities

(无 —— account-auth 现有要求为"写入本地配置",不限定位置;akm-node 行为面无其他 spec 级变更。)

## Impact

- **代码**:`src/node/app/config.py`(env 文件解析顺序)、`src/node/app/login.py`(写入目标路径)、`src/node/app/__main__.py`(提示文案);server/web 无代码改动。
- **构建/基建**:`src/Dockerfile`、`src/Dockerfile.node`、新增 `src/.dockerignore`、`.github/workflows/release.yml`、`scripts/install-akm-node.{sh,ps1}`、`scripts/build-release.ps1`(本地构建入口)。
- **依赖**:无新增运行时依赖;akm-node wheel 声明对 `akm-shared` 的依赖由 Release 的 find-links 满足。
- **文档**:`docs/deployment.md` 新增;`README.md` 增加部署章节链接。
- **不受影响**:REST/WS/MCP/Context API 契约均不变,无需同步 `docs/api-reference.md`。
