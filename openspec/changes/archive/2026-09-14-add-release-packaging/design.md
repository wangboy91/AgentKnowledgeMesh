# 设计:打包发布 v0.2.0

## Context

当前部署现状:Hub 已有 [src/Dockerfile](../../../src/Dockerfile)(前端构建→静态文件→server 单镜像)与 SQLite 默认 compose;node 有 [src/Dockerfile.node](../../../src/Dockerfile.node)。仓库公开于 `github.com/wangboy91/AgentKnowledgeMesh`(已验证可匿名访问),git remote 为 SSH。约束:

- `akm-node` 的 `pyproject.toml` 通过 `[tool.uv.sources]` 把 `akm-shared` 声明为 path 依赖(`../shared`)——本地 `uv sync` 可用,但远程安装必须同时提供两个 wheel;
- `src/node/app/config.py` 的 `BASE_DIR` 锚定在包安装目录,`uv tool install` 后落在 venv 的 site-packages,升级即丢;
- server 首启管理员引导(`ensure_admin_user`)、静态资源服务、节点 login/register 流程均已具备,本变更不动这些行为面。

## Goals / Non-Goals

**Goals**
- 发版产物自动化:打 tag → Actions 产出 wheel × 2、GHCR 镜像、GitHub Release(含安装脚本与部署 compose)。
- 任意机器一条命令安装 `akm-node`(bash + PowerShell 双脚本),凭证升级不丢。
- 镜像构建卫生:不泄密、不带开发产物。

**Non-Goals**
- 不做 PyPI 发布(名字永久占用、需账号,公共 GitHub Release 已满足需求)。
- 不做多架构镜像(当前部署目标 x86_64;`platform` matrix 留待需要时加)。
- 不改 REST/WS/MCP 契约,不做 server/web 代码改动。
- 不引入版本清单/自动升级机制(升级 = 重新执行安装脚本)。

## Decisions

### D1:分发渠道 = GitHub Release + GHCR(而非 PyPI / git clone)

- **选择**:tag 触发 Actions;wheel 上传 Release 资产,镜像推 GHCR。
- **理由**:仓库已公开,匿名可下载;无需 PyPI 账号;发版、回滚(重新发 tag)、私有化(以后转私有只需脚本加 token)都可控。
- **备选**:
  - PyPI:`uv tool install akm-node` 最简,但名字永久公开占用、发版流程更重,放弃;
  - git clone + `uv tool install ./src/node`:无需构建产物,但把整个仓库(含 web/docs)拉到用户机器,且依赖 git 与网络到 GitHub 仓库本身,放弃。

### D2:akm-shared 依赖解析 = 安装脚本 `--find-links` 本地 wheel 目录

- **选择**:脚本下载 Release 中的 `akm_shared-*.whl` 与 `akm_node-*.whl` 到临时目录,执行 `uv tool install akm-node --find-links <dir>`(升级时 `--reinstall` 或先 `uv tool uninstall`)。
- **理由**:node wheel 的元数据依赖 `akm-shared`,uv 在 find-links 目录即可闭包解析;仓库内 `uv sync` 的 path 映射不受影响(仅作用于 uv 的 workspace 解析,不进 wheel 元数据)。
- **备选**:把 akm_shared 两个模块 vendor 进 node 包——单 wheel 更简,但 shared 代码双份漂移(mcp 工具格式化两侧需一致),放弃。

### D3:凭证位置 = `~/.akm-node/.env`,env 解析顺序为 `[仓库 .env, 用户 .env]`,写入只写用户文件

- **选择**:`config.py` 增加 `USER_ENV_FILE`(`AKM_NODE_ENV_FILE` 覆盖,默认 `~/.akm-node/.env`)与 `USER_STATE_DIR`(`AKM_NODE_STATE_DIR` 覆盖);`NodeSettings.model_config["env_file"] = [BASE_DIR/".env", USER_ENV_FILE]`(pydantic-settings 列表后者优先);`login.py` 的 `_update_env` 目标从 `BASE_DIR/".env"` 改为 `USER_ENV_FILE`。
- **同类的快照问题**:`state.py` 的同步快照原锚定 `<node 包>/data/`,安装版升级即丢 → 退化为全量重扫。修复:`resolve_snapshot_path()` 选择"开发仓已有快照用原位置,否则 `~/.akm-node/sync_state.json`"(实现中发现的补充修复,已补入 spec/tasks)。
- **理由**:安装版 BASE_DIR 在 venv 内不可靠;开发场景仓库 `.env` 仍被读取(存在且未配置用户文件时生效);`AKM_NODE_ENV_FILE` 提供完全覆盖的逃生口。写入只写用户文件,避免安装版把凭证写进 site-packages。
- **备选**:只认用户目录、不兼容仓库 .env —— 会破坏现有开发者习惯(凭证已在 `src/node/.env`),放弃。

### D4:镜像构建 = 现有双阶段 Dockerfile 修补,不重写

- 修 `src/.dockerignore`(放 `src/` 构建上下文根):排除 `**/.venv`、`**/node_modules`、`**/__pycache__`、`server/tests`、`server/eval`、`node/tests`、`**/.env`、`server/data`、`node/data`。`server/.env` 从此不进镜像层。
- uv 固定版本(`ghcr.io/astral-sh/uv:0.12.5`),避免 `latest` 漂移破坏构建。
- **torch CPU 化(实现中发现)**:`sentence-transformers` 依赖的 torch 在 Linux PyPI 轮子捆绑 CUDA(nvidia 3.2G + torch 1.1G + triton 0.9G),镜像达 9.7G。处理:`uv sync` 后**同一层内** `uv pip install torch==$VER --torch-backend=cpu --reinstall-package torch` 并卸载 nvidia/triton 组件(必须同层,Docker 后层删除不减小镜像);uv 下载缓存走 BuildKit `--mount=type=cache`(否则 6.5G 缓存进层);层内以 `import torch; assert '+cpu'` 自检。构建时先下载 CUDA torch 仅为取版本号,一次性成本,Actions 网络快可忽略。瘦身效果:venv 5.8G→1.5G。
- Actions 构建镜像用 `src/` 为 context(与本地一致),推 `ghcr.io/wangboy91/akm-hub:<tag>` 与 `:latest`。
- **部署编排双 compose(补充)**:RAG 语义检索依赖 PostgreSQL + pgvector,SQLite 模式下 RAG 降级不可用(语义接口返回错误,启动日志告警)。随 Release 分发两个 compose:SQLite 版(零依赖,无 RAG)与 PostgreSQL 版(`pgvector/pgvector:pg16`,含 RAG);README 与部署文档均显著标注该能力差异。仓库 `src/docker-compose.pg.yml` 原用 `postgres:16-alpine`(无 pgvector 扩展,RAG 初始化必失败),已修为 pgvector 官方镜像。

### D5:安装脚本策略

- bash 脚本:检测 `uv`(`command -v`)→ 缺失则 `curl .../install.sh | sh` 官方安装;`GitHub API` 取最新 release(或 `AKM_VERSION` 环境变量锁定)→ 下载两 wheel 到临时目录 → `uv tool install akm-node --find-links ...`(已装则 `--upgrade`)→ 打印 `akm-node login` 引导。
- PowerShell 脚本同理(`winget`/官方 `irm https://astral.sh/uv/install.ps1`)。
- 脚本随仓库维护(`scripts/`),发版时由 Actions 复制进 Release 资产,保证"一条命令"URL 指向 Release 而非分支(可复现)。

### D6:发布流程(用户手工触发,CI 只做产物)

按项目铁律 AI 不执行 commit/push:实现完成后由用户 commit → push → `git tag v0.2.0 && git push origin v0.2.0`,Actions 产物落 GHCR + Release。

## Risks / Trade-offs

- [Actions 无权限推 GHCR / 建 Release] → workflow 使用 `GITHUB_TOKEN`(`permissions: packages: write, contents: write`);首次推送 GHCR 包默认私有时在仓库设置里改为 public(部署文档中写明)。
- [pydantic-settings 列表 env_file 优先级记反] → 实现时以测试验证"两文件并存时用户文件覆盖仓库文件"。
- [uv tool install --find-links 解析失败(uv 版本差异)] → 安装脚本安装的是最新 uv;实现阶段在 Windows 实机验证完整链路。
- [Windows PowerShell 执行策略限制远程脚本] → 文档同时给出"下载后本地执行"与 `powershell -ExecutionPolicy Bypass -File` 两种方式。
- [node wheel 版本与 shared wheel 版本错配] → 两者同次 Release 一起产出,脚本按同一 Release 下载,天然一致。

## Migration Plan

1. 合入本变更 → 用户打 `v0.2.0` tag → Actions 出产物(首个 Release)。
2. 已有部署(本地 `uv run` 开发):无需迁移,仓库 `.env` 继续生效。
3. 回滚:compose 固定版本 tag,回滚 = 改回旧 tag 重启;akm-node 回滚 = `AKM_VERSION=<旧版>` 重跑安装脚本。

## Open Questions

(无 —— 多架构镜像与私仓 token 支持均为后续可选增强,不影响本次方案。)
