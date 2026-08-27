## Why

Node 客户端目前仍是 4 个平铺脚本（`main.py`/`config.py`/`scanner.py`/`hub_client.py`），与已重构成 `app/` 包结构的 Hub 端不一致：打包配置 `packages = ["."]` 有隐患、入口是 `python main.py` 而非可安装的 console script，且扫描器与 Hub 端是两份几乎重复的代码。同时全仓库仍残留 `agentvault-*` 品牌（项目已更名为 AgentKnowledgeMesh），环境变量前缀 `AV_` 是旧品牌 AgentVault 的缩写。这是一次零行为变更的结构对齐 + 品牌统一 + 去重重构。

## What Changes

- **Node 包化**：将 `src/node/` 的 4 个平铺脚本重组织为 `app/` 包（`__main__.py` 入口、`config.py`、`transport.py`、`sync.py`、`runner.py`），入口从 `python main.py` 改为可安装的 console script `akm-node`（`python -m app` 同样可用），`packages` 从 `["."]` 改为 `["app"]`。
- **品牌统一**（**BREAKING**：部署命名与环境变量前缀变化，提供向后兼容别名）：`agentvault-*` → `akm-*`。
  - pyproject：`agentvault-server` → `akm-server`、`agentvault-node` → `akm-node`；console script `agentvault` → `akm-hub`。
  - Docker：compose service/container/volume 名 `agentvault`/`agentvault-node`/`agentvault-postgres`/`agentvault-data` → `akm-*`。
  - 环境变量前缀 `AV_` → `AKM_`（旧 `AV_` 前缀作为弃用别名继续生效，见 design）。
  - 数据库默认数据标识（`data/agentvault.db`、库名 `agentvault`）**保持不动**以保证既有部署兼容。
- **抽取共享扫描器**：将 Hub 与 Node 两份重复的 Markdown 扫描器合并为独立包 `akm-shared`（`src/shared/`），Hub 端 `app/services/scanner.py` 退化为注入配置的薄包装，Node 端直接复用。
- **顺带修复**：`src/Makefile` 的 `dev-backend`/`dev` 目标仍执行已不存在的 `server/main.py`（上次 Hub 重构遗留），本次一并修正为 `akm-hub` / `python -m app`。

## Capabilities

### New Capabilities

（无新能力——本次为纯结构重构与品牌统一，不引入新的系统行为。）

### Modified Capabilities

- `knowledge-indexing`: 环境变量前缀 `AV_` 变更为 `AKM_`（涉及 `AV_MAX_FILE_SIZE_MB`、`AV_KNOWLEDGE_ROOTS`、`AV_DB_TYPE` 及连接参数）。
- `vector-search`: 环境变量前缀 `AV_` 变更为 `AKM_`（涉及 `AV_VECTOR_DIMENSIONS`、`AV_EMBEDDING_PROVIDER`、`AV_ARK_API_KEY`）。
- `multi-node-sync`: 环境变量前缀 `AV_` 变更为 `AKM_`（涉及 `AV_NODE_ID`、`AV_NODE_NAME`、`AV_HEARTBEAT_INTERVAL`）。

## Impact

- **代码**：`src/node/`（包化、模块拆分）、`src/server/app/services/scanner.py`（薄包装）、新增 `src/shared/`。
- **打包**：`src/node/pyproject.toml`、`src/server/pyproject.toml`（名称、console script、依赖 `akm-shared`）、新增 `src/shared/pyproject.toml`。
- **部署**：`src/Dockerfile`、`src/Dockerfile.node`、`src/docker-compose.yml`、`src/docker-compose.pg.yml`、`src/docker-compose.node.yml`、`src/Makefile`。
- **配置**：`src/server/app/config.py`、`src/node/app/config.py`（env 前缀 `AKM_` + `AV_` 弃用别名）。
- **文档**：`README.md`、`AGENTS.md`、`src/server/MCP_USAGE.md`、`src/node/.env.example` 中的 `agentvault`/`AV_` 引用。
- **测试**：`src/server/tests/test_smoke.py`（沿用 `agentvault.db` 默认断言不受影响，可增补前缀别名断言）。
