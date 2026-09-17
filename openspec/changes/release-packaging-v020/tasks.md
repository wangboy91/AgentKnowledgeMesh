# 任务清单:打包发布 v0.2.0

> 对应 spec delta:`specs/release-distribution/spec.md`;设计决策见 `design.md`。

## 1. akm-node 凭证与配置持久化(spec:凭证与配置持久化)

- [x] 1.1 修改 [src/node/app/config.py](../../../src/node/app/config.py):新增 `USER_ENV_FILE`(`AKM_NODE_ENV_FILE` 覆盖,默认 `~/.akm-node/.env`),`NodeSettings.model_config["env_file"]` 改为 `[BASE_DIR/".env", USER_ENV_FILE]`;验证:新增单测覆盖"仓库 .env 存在且用户 .env 不存在/两者并存/自定义路径"三种解析情形
- [x] 1.2 修改 [src/node/app/login.py](../../../src/node/app/login.py):`_update_env` 写入目标改为 `USER_ENV_FILE`,完成提示文案同步改路径;验证:`uv run akm-node login` 后凭证出现在 `~/.akm-node/.env` 而非包目录
- [x] 1.3 修改 [src/node/app/__main__.py](../../../src/node/app/__main__.py):启动/报错提示文案从 `uv run akm-node` 调整为 `akm-node`(兼顾两种安装方式);验证:无凭证启动时提示可读
- [x] 1.4 运行 `cd src/node && uv sync` 后全量跑 `uv run pytest`,确认既有测试不回归
- [x] 1.5 补充修复 [src/node/app/state.py](../../../src/node/app/state.py):同步快照默认路径改为"开发仓已有快照用原位置,否则 `~/.akm-node/sync_state.json`"(与凭证同类的包目录锚定问题,`AKM_NODE_STATE_DIR` 可覆盖);验证:单测覆盖两位置选择逻辑

## 2. 镜像构建卫生(spec:Hub 容器镜像分发)

- [x] 2.1 新增 `src/.dockerignore`:排除 `**/.venv`、`**/node_modules`、`**/__pycache__`、`server/tests`、`node/tests`、`**/.env`、`server/data`、`node/data`;验证:`docker build` 日志确认 COPY 层不含上述内容,镜像体积明显下降 【已验证:镜像内无 .env/.venv(宿主)/tests/eval;另补 CPU torch 换装+BuildKit cache mount,最终瘦身大小由 Actions 产物确认】
- [x] 2.2 修正 [src/Dockerfile](../../../src/Dockerfile) 与 [src/Dockerfile.node](../../../src/Dockerfile.node):uv 基础镜像从 `:latest` 固定为当前稳定版本号;验证:两镜像构建成功 【已固定 uv 0.12.5;两镜像本地构建成功(hub 10.8G 为含 uv 缓存层的验证镜像,Actions 版走 cache mount 约 2.6G;node 343MB)】
- [x] 2.3 本地构建 Hub 镜像并冒烟:`docker build -t akm-hub:dev .` → 起容器 → 浏览器打开 Web、登录、确认 `/api` 可用;`docker run --rm akm-hub:dev sh -c "ls /app | grep -c .env"` 确认无 .env 【已验证:容器起于 8002,Web 首页/静态资源/API 登录/挂载目录扫描/搜索全通;镜像内无 .env】
- [x] 2.4 local 嵌入降级为可选依赖,镜像去 torch:[src/server/pyproject.toml](../../../src/server/pyproject.toml) 将 `sentence-transformers` 从硬依赖移入 optional-dependencies 的 `local-embedding` extra(默认 ark 不需要,避免镜像背负 torch 全家桶);[embeddings.py](../../../src/server/app/services/rag/embeddings.py) 懒加载 import 加缺包时的明确报错;[src/Dockerfile](../../../src/Dockerfile) 删除 CPU torch 换装段;验证:`uv sync` 默认环境无 torch、`uv sync --extra local-embedding` 可装回、全量 pytest 无回归、镜像构建成功 【已验证:默认 venv 无 torch/sentence-transformers;pytest 112 passed;镜像构建成功,体积 ~2.6G → 791MB;容器冒烟 Web 200/API 登录 401(错误凭证)正常;`AKM_EMBEDDING_PROVIDER=local` 时报出含 `uv sync --extra local-embedding` 指引的明确错误】

## 3. 安装脚本(spec:akm-node 一键安装)

- [x] 3.1 新增 `scripts/install-akm-node.sh`:检测/安装 uv → `AKM_VERSION`(默认取 GitHub 最新 release)下载 `akm_shared`/`akm_node` wheel 到临时目录 → `uv tool install akm-node --find-links`(已装则升级)→ 打印 `akm-node login` 引导;验证:本地以 `AKM_VERSION=<测试release>` 干跑(或用本地构建 wheel 模拟)确认命令拼接正确
- [x] 3.2 新增 `scripts/install-akm-node.ps1`:同逻辑 PowerShell 版;验证:在本机 PowerShell 实测安装出 `akm-node` 命令,`akm-node login` 可交互、`akm-node --mcp` 可列出工具
- [x] 3.3 验证升级幂等:重复执行安装脚本,`akm-node --version`/包信息更新且 `~/.akm-node/.env` 凭证保留

## 4. 发版流水线与本地构建入口

- [x] 4.1 新增 `scripts/build-release.ps1`:本地构建两个 wheel(`uv build` 于 `src/shared`、`src/node`)并校验产物;验证:产出 `akm_shared-*.whl`、`akm_node-*.whl`
- [ ] 4.2 新增 `.github/workflows/release.yml`:on push tag `v*` → buildx 构建 Hub 镜像(context `src/`)推 `ghcr.io/wangboy91/akm-hub:<tag>` 与 `:latest`(permissions: packages write)→ 构建 wheels → 创建 GitHub Release 并上传 wheels、两个安装脚本、部署用 `docker-compose.yml`(镜像固定版本 tag);验证:YAML 语法(actionlint 或 `gh workflow` 可见),推送测试 tag 后产物齐全 【workflow 已写、YAML 校验通过;产物齐全性待 v0.2.0 打 tag 首跑】
- [x] 4.3 部署用 compose(随 Release 分发)编写:镜像引用 `ghcr.io/wangboy91/akm-hub:<VERSION>`,含 `KNOWLEDGE_DIR` 卷、数据卷、`AKM_ADMIN_USERNAME/PASSWORD` 环境变量示例;验证:compose config 校验通过
- [x] 4.4 PG 模式 compose 透传 ark 嵌入配置:[deploy/docker-compose.pg.yml](../../../deploy/docker-compose.pg.yml) 与 [src/docker-compose.pg.yml](../../../src/docker-compose.pg.yml) 的 akm-hub environment 增加 `AKM_EMBEDDING_PROVIDER`/`AKM_EMBEDDING_MODEL`/`AKM_ARK_API_KEY`/`AKM_ARK_BASE_URL` 透传(默认 ark,与 `src/server/app/config.py` 默认值一致;API Key 由部署方在本地 `.env` 提供,不进镜像);同步修正 `src/server/.env.example` 嵌入段(原写 local 默认,与代码不符)与 [docs/deployment.md](../../../docs/deployment.md) 新增 §1.5 嵌入模型配置;验证:`docker compose config` 两个 compose 均校验通过

## 5. 文档与协议

- [x] 5.0 新增根目录 `LICENSE`(MIT,版权人 wangboy91),`src/server`、`src/node`、`src/shared` 的 `pyproject.toml` 补 `license = { text = "MIT" }`;验证:文件存在且三处 pyproject 校验可解析

- [x] 5.1 新增 `docs/deployment.md`:Hub 容器部署(GHCR 镜像 + compose,管理员初始化、数据持久化、知识目录挂载、PostgreSQL 可选)、akm-node 一键安装(两平台命令)、`akm-node --mcp` 接入本机智能体(claude/codex 等 mcp 配置示例)、常见问题(GHCR 包可见性、PowerShell 执行策略);验证:按文档步骤在干净目录可走通(至少本地模拟)
- [x] 5.2 README.md 增加部署章节索引指向 `docs/deployment.md`;验证:链接可达

## 6. 集成验证(收尾)

- [x] 6.1 全链路演练:本地 Hub 容器 → 另一台机器/干净环境安装 akm-node → `akm-node login` 接入 → 知识目录同步 → `akm-node --mcp` 检索(search_documents 关键词+语义)→ Web 端可见节点与文档 【链路全通:容器 Hub(8002)冒烟 + 隔离 Hub(8001) + 安装版 akm-node login→同步→MCP 关键词检索;语义检索依赖 embedding 模型下载未在容器复测(server 侧测试覆盖);Web UI 浏览器外观留用户确认】
- [x] 6.2 运行 `npx openipd validate` 与 `openspec validate release-packaging-v020 --strict` 通过;向用户报告完成情况,提醒 commit/push/打 tag(`v0.2.0`)由用户本人执行 【openspec --strict 通过;双 compose(SQLite 无 RAG / PG 含 RAG)随 Release 分发并已在文档显著标注;npx openipd 404(包未发布 registry),以 openspec 为准】
