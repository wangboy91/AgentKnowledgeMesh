## Context

见 proposal.md 的 Why。当前 Node 端是 4 个平铺脚本，Hub 端已是 `app/` 包结构；两份扫描器几乎重复（差异仅 `source` 字段、max_size 来源、顶层函数签名）；`AV_`/`agentvault` 品牌残留散布于打包、Docker、配置与文档。本次为纯重构 + 品牌统一，**不改变任何系统行为**（除 env 前缀新增别名外，行为等价）。

## Goals / Non-Goals

**Goals:**
- Node 与 Hub 对齐为可安装的 `app` 包 + console script，消除 `packages = ["."]` 隐患。
- 扫描器单一来源（`akm-shared`），Hub 与 Node 共用。
- 品牌从 `agentvault`/`AV_` 迁移到 `akm`/`AKM_`，且不破坏既有 `.env` 与既有数据文件。

**Non-Goals:**
- 不实现 Node→Hub 的文档入库（属 `add-node-http-sync`，`sync_documents()` 的 TODO 原样保留）。
- 不改数据库默认数据标识（`data/agentvault.db`、库名 `agentvault`）。
- 不引入 uv workspace（维持两个独立可部署单元的现状）。
- 不改 Node 扫描行为（仍为 10MB 硬上限，不做 `max_file_size_mb` 可配置化）。

## Decisions

### 1. Node 目标结构：平铺 `app/` 模块，不做 `services/` 子目录
Node 体量小（约 4 个职责模块），过度嵌套得不偿失。按职责拆成 4 个模块镜像 Hub 的"入口/配置/传输/同步/编排"划分：

```
src/node/
├── pyproject.toml          # akm-node，packages=["app"]，[project.scripts] akm-node
├── .env.example
├── .python-version
└── app/
    ├── __init__.py
    ├── __main__.py         # main() + 启动横幅（原 main.py）
    ├── config.py           # NodeSettings（AKM_ 前缀 + AV_ 别名；env_file 锚定项目根）
    ├── transport.py        # connect/register/disconnect/heartbeat/消息接收循环（原 hub_client 的传输职责）
    ├── sync.py             # scan + sync_documents（TODO 保留）+ send_doc_content（原 hub_client 的同步职责）
    └── runner.py           # run() 主循环 + 5s 重连编排（原 hub_client 的编排职责）
```

备选：保留单文件 `hub_client.py` 仅改 import 与 `packages`。否决——那没完成"与 Hub 结构对齐"，且三个职责继续耦合，`add-node-http-sync` 时仍需拆。

### 2. 共享扫描器：独立包 `akm-shared`，path 依赖（非 workspace）
`src/shared/pyproject.toml` 定义 `akm-shared`（`packages=["akm_shared"]`），模块 `akm_shared/scanner.py` 提供参数化的扫描逻辑：

- `ScannedDocument`（含 `source` 字段）
- `extract_title(content, filename)`、`compute_hash(content)`
- `scan_single_root(root, prefix="", max_size_bytes=...)`
- `scan_knowledge_roots(roots, max_size_bytes=...)`（单目录不加前缀，多目录以目录名为前缀）

两个项目在 pyproject 中以 `[tool.uv.sources] akm-shared = { path = "../shared" }` 引用（非 editable，安装进 site-packages，运行时不依赖源目录）。

备选：uv workspace（根 pyproject + members）——否决，会迫使两处 `uv sync`/Docker/`.venv` 布局重排，收益低于成本。备选：path 依赖 editable——否决，运行期依赖源目录，Docker 镜像更脆。

### 3. Hub 端扫描器退化为薄包装，保持调用点零改动
`src/server/app/services/scanner.py` 改为：`from akm_shared.scanner import ScannedDocument, extract_title, compute_hash`，并保留 `async def scan_knowledge_root()`，内部调用 `akm_shared.scanner.scan_knowledge_roots(settings.knowledge_paths, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)`。保留 `async` 签名与 `ScannedDocument` 再导出，使 `api/documents.py`（`scan_knowledge_root`）与 `indexer.py`（`ScannedDocument`）无需改动。

### 4. 环境变量前缀：`AKM_` 为主，`AV_` 弃用别名
两个 config 类的 `env_prefix` 改为 `AKM_`，同时为每个字段设置 `validation_alias=AliasChoices("AKM_X", "AV_X")`，使旧 `AV_` 环境变量继续生效（向后兼容）。数据库默认数据标识不动（见 Non-Goals）。

备选：硬切换 `AV_` → `AKM_` 不留别名——否决，会静默丢弃既有部署的 `.env` 配置。备选：自定义 env source 支持双前缀——否决，比 `AliasChoices` 复杂且不直观。

### 5. 入口与 Docker：console script 供本地开发，Docker 用模块路径
- 本地：`uv run akm-hub`（server）、`uv run akm-node`（node）、`python -m app` 均可。
- Docker：两处 `Dockerfile` 保留 `uv sync --no-dev --no-install-project`（不安装项目本体，故不装 console script）。server CMD 沿用 `uvicorn app.main:app`；node CMD 从 `python main.py` 改为 `python -m app`。
- Docker 依赖共享包：两处 Dockerfile 在 `uv sync` 前新增 `COPY shared/ ../shared/`，使 `path = "../shared"` 可解析；非 editable 安装后无需运行期源目录。

### 6. 命名对照表

| 关注点 | 旧 | 新 |
|---|---|---|
| server pyproject | `agentvault-server` | `akm-server` |
| node pyproject | `agentvault-node` | `akm-node` |
| 共享 pyproject | — | `akm-shared` |
| server console script | `agentvault` | `akm-hub` |
| node console script | （无，`python main.py`） | `akm-node` |
| compose server service/container | `agentvault` | `akm-hub` |
| compose pg container | `agentvault-postgres` | `akm-postgres` |
| compose node service/container | `agentvault-node` | `akm-node` |
| compose volume | `agentvault-data` | `akm-hub-data` |
| env 前缀 | `AV_` | `AKM_`（`AV_` 弃用别名） |
| DB 默认文件/库名 | `data/agentvault.db` / `agentvault` | 不变 |

## Risks / Trade-offs

- [`AV_` 别名实现出错（如 `AliasChoices` 与 `env_prefix` 交互导致旧变量失效）] → 在 `test_smoke.py` 增补一条断言：用 `AV_` 与 `AKM_` 两种前缀读取同一字段均生效。
- [共享包引入导致 Docker 构建缺 `shared/` 目录而 `uv sync` 失败] → Dockerfile 显式 `COPY shared/ ../shared/`，并在 apply 阶段以 `docker compose build` 验证。
- [Node 拆分 transport/sync/runner 时逻辑漂移] → 逐函数搬迁不改实现，apply 后以 `akm-node` 连本地 Hub 冒烟验证。
- [Node `env_file` 由 CWD 相对改为锚定项目根] → 更稳健（server 已是此模式）；仅影响"从其他目录运行且依赖 CWD `.env`"的罕见用法，收益大于风险。

## Migration Plan

1. 先落 `akm-shared` 与 server 薄包装（server 行为不变），跑 `pytest`。
2. 再落 node `app/` 包 + 模块拆分 + `akm-node` 入口，`uv run akm-node` 冒烟。
3. 再落品牌重命名（pyproject/compose/Dockerfile/config 前缀/文档）。
4. 验证：`pytest`、`docker compose build`、`docker compose -f docker-compose.node.yml build`、`make dev-backend`/`make dev-node`。
5. 回滚：本变更无数据迁移，`git revert` 即可；既有 `.env` 因 `AV_` 别名无需改动。

## Open Questions

（无——所有影响 spec/结构/任务的决策已在此确定。）
