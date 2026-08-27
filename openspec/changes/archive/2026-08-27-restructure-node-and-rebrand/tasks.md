## 1. 共享扫描器 akm-shared

- [x] 1.1 新建 `src/shared/pyproject.toml`（name=`akm-shared`、`packages=["akm_shared"]`）与 `src/shared/akm_shared/__init__.py`、`akm_shared/scanner.py`（`ScannedDocument` 含 `source` 字段、`extract_title`、`compute_hash`、`scan_single_root(root, prefix="", max_size_bytes=...)`、`scan_knowledge_roots(roots, max_size_bytes=...)`），验证 `cd src/shared && uv sync && uv run python -c "from akm_shared.scanner import scan_knowledge_roots"` 通过

## 2. Hub 端接入共享扫描器

- [x] 2.1 将 `src/server/app/services/scanner.py` 改为薄包装：从 `akm_shared.scanner` 再导出 `ScannedDocument`/`extract_title`/`compute_hash`，保留 `async def scan_knowledge_root()` 内部调用 `scan_knowledge_roots(settings.knowledge_paths, max_size_bytes=settings.max_file_size_mb * 1024 * 1024)`，验证 `cd src/server && uv run pytest -q` 通过且 `api/documents.py`、`indexer.py` 无需改动
- [x] 2.2 在 `src/server/pyproject.toml` 添加依赖 `akm-shared` 并配置 `[tool.uv.sources] akm-shared = { path = "../shared" }`，验证 `cd src/server && uv sync` 成功解析

## 3. Node 端包化

- [x] 3.1 新建 `src/node/app/__init__.py`，迁移 `config.py` → `app/config.py`（`env_file` 锚定项目根目录；`env_prefix` 改为 `AKM_` 并为每个字段加 `validation_alias=AliasChoices("AKM_X","AV_X")` 弃用别名），验证 `cd src/node && uv run python -c "from app.config import settings; print(settings.hub_url)"` 通过
- [x] 3.2 将 `hub_client.py` 拆分为 `app/transport.py`（connect/register/disconnect/send_heartbeat/handle_messages）、`app/sync.py`（`sync_documents` 保留 TODO 注释、`send_doc_content`，改用 `akm_shared.scanner` 扫描）、`app/runner.py`（`run()` 主循环 + 5s 重连编排），验证 `python -m app` 可启动无 import 错误
- [x] 3.3 新建 `app/__main__.py`（`main()` 与启动横幅，迁移自原 `main.py`），删除平铺的 `main.py`/`scanner.py`/`hub_client.py`/`config.py`，验证 `cd src/node && uv run python -m app` 打印横幅并进入连接流程
- [x] 3.4 改写 `src/node/pyproject.toml`：`name="akm-node"`、`packages=["app"]`、`[project.scripts] akm-node = "app.__main__:main"`、添加 `akm-shared` 依赖与 `[tool.uv.sources]` path 源，验证 `cd src/node && uv run akm-node` 启动

## 4. 品牌重命名（打包 / Docker / 文档）

- [x] 4.1 改 `src/server/pyproject.toml`：`name="akm-server"`、`[project.scripts] akm-hub = "app.__main__:main"`（替换原 `agentvault`），验证 `cd src/server && uv run akm-hub` 启动
- [x] 4.2 改 `src/server/app/config.py`：`env_prefix` 改为 `AKM_` 并为每个字段加 `validation_alias=AliasChoices("AKM_X","AV_X")` 弃用别名，验证 `cd src/server && uv run pytest -q` 通过
- [x] 4.3 在 `src/server/tests/test_smoke.py` 增补断言：同一字段经 `AKM_` 与 `AV_` 两种前缀读取结果一致，验证 `uv run pytest -q` 通过
- [x] 4.4 更新 `src/Dockerfile`：`COPY shared/ ../shared/` 置于 `uv sync` 前、`ENV AV_*` 改 `ENV AKM_*`，验证 `cd src && docker compose build` 成功
- [x] 4.5 更新 `src/Dockerfile.node`：`COPY shared/ ../shared/`、`CMD` 改为 `["uv","run","python","-m","app"]`、`ENV` 前缀改 `AKM_`，验证 `cd src && docker compose -f docker-compose.node.yml build` 成功
- [x] 4.6 更新 `src/docker-compose.yml`、`src/docker-compose.pg.yml`、`src/docker-compose.node.yml`：service/container/volume 名 `agentvault`→`akm-hub`、`agentvault-node`→`akm-node`、`agentvault-postgres`→`akm-postgres`、`agentvault-data`→`akm-hub-data`，验证 `cd src && docker compose config -q && docker compose -f docker-compose.node.yml config -q` 通过
- [x] 4.7 修正 `src/Makefile` 的 `dev`/`dev-backend`/`dev-node` 目标（`server/main.py` 已不存在，改为 `cd server && uv run akm-hub`；`node/main.py` 改为 `cd node && uv run akm-node`），验证 `cd src && make -n dev-backend dev-node` 展示正确命令
- [x] 4.8 更新文档 `README.md`、`AGENTS.md`、`src/server/MCP_USAGE.md`、`src/node/.env.example` 中的 `agentvault`/`AV_` 引用（保留数据库默认数据标识与历史注释），验证 `grep -rniE 'agentvault|uv run agentvault' src README.md AGENTS.md` 仅命中 `data/agentvault.db`、库名 `agentvault` 与说明性注释
