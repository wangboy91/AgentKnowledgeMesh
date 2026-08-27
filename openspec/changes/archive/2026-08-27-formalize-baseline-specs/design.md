## Context

AgentKnowledgeMesh 已完成 V0.1（单机知识库）、V0.2（Hub+Node 多节点）、V0.3（Agent 集成：Context API / MCP / RAG / 文档转换 / 在线编辑）。2026-08-27 仓库重组时，过时的自由格式 openspec 文档被删除并归档至 `openspec/changes/archive/`，`openspec/` 以 `spec-driven` schema 重新初始化，主规格目录 `openspec/specs/` 目前为空。

本变更是**纯文档变更**：通过阅读现有代码，把已交付的系统行为固化为 8 个能力的 spec-driven 基线规格。所有需求描述均从代码逐行核对得出（`src/server/app/`、`src/node/`），不引入任何代码改动。

**已核对的关键事实**（写规格的依据）：

- API 前缀 `/api`，路由组：`/documents`、`/search`、`/nodes`、`/context`、`/mcp`、`/rag`、`/convert`，另有 `/api/health`、`/api/stats`、WebSocket `/ws`
- 配置统一走 `AV_` 环境变量前缀（`app/config.py`）；数据库 `sqlite`（默认）/ `postgres` 可切换；知识库目录默认 `~/Knowledge`
- 向量存储使用 PostgreSQL + pgvector，连接参数未配置时 fallback 到主库；嵌入供应商 `ark`（默认，doubao-embedding-vision-250615）/ `local` 可切换；向量维度自动检测，模型切换时自动重建表
- Node 客户端：node_id 由 `uuid5(hostname)` 生成，心跳默认 30 秒，断线 5 秒重连

## Goals / Non-Goals

**Goals:**

- 为 8 个已实现能力各产出一份 `## ADDED Requirements` 格式的 delta spec，逐条需求可回溯到具体代码文件
- 记录已发现的功能缺口与实现现状（见下方"已知缺口"），为后续变更提供起点
- 完成后可通过 `/opsx:sync` 合并为 `openspec/specs/` 主规格，重建完整的 spec-driven 工作流基线

**Non-Goals:**

- 不修改任何代码、数据库、依赖——发现缺口只记录、不修复
- 不为前端纯展示细节（主题切换、侧边栏拖拽等）建立需求；仅覆盖有后端行为支撑的能力
- 不规划 V1.0 知识图谱、测试补充等未来工作（它们是后续独立变更）

## Decisions

### 1. 能力切分：8 个能力，按行为边界而非代码模块

| 能力 | 覆盖范围 | 主要代码来源 |
|------|----------|--------------|
| `knowledge-indexing` | 扫描、标题提取、增量索引、存储切换、知识库目录配置 | `services/scanner.py`、`services/indexer.py`、`config.py` |
| `document-management` | 文档列表/文件树/详情/创建/更新 + 统计与健康检查 | `api/documents.py`、`api/__init__.py`、`main.py` |
| `keyword-search` | ILIKE 关键词搜索与排序 | `api/search.py` |
| `multi-node-sync` | WebSocket 协议、注册/心跳、节点管理 API、Node 客户端行为 | `services/websocket.py`、`api/nodes.py`、`src/node/` |
| `agent-context-api` | `/api/context` prompt 注入上下文 | `api/context.py` |
| `mcp-integration` | MCP Server（SSE + stdio）与 3 个工具 | `api/mcp.py`、`services/mcp_server.py` |
| `vector-search` | RAG 语义搜索、向量索引、pgvector 存储管理 | `api/rag.py`、`services/rag/` |
| `document-conversion` | PDF/Word/HTML 上传转换、URL 抓取转换 | `api/convert.py`、`services/converters/` |

**备选方案**：单一巨型规格（难以增量演进，弃用）；按 API 路由逐端点建能力（粒度过细、跨端点行为被割裂，弃用）。

### 2. 代码是唯一事实来源

归档的旧文档（`2026-08-27-legacy-design-docs/`）仅作背景参考。凡是旧文档与代码不一致处（如旧 `api.md` 缺少 `/context`、`/rag` 端点；旧文档中的 `server/` 路径已不存在），一律以代码为准。

### 3. 已实现行为照实描述，缺口显式记录而非粉饰

规格描述系统**当前**行为。代码中的未完成项（见"已知缺口"）不写入需求正文，统一记录在本设计文档，作为后续变更的输入。

### 4. 语言约定

沿用代码库风格：OpenSpec 结构关键字（`## ADDED Requirements`、`### Requirement:`、`#### Scenario:`、SHALL、WHEN/THEN）保持英文；需求描述与场景内容用中文。需求标题用简短英文以便引用。

## 已知缺口（核对代码时发现，留作后续变更）

1. **Node 文档上行同步未实现**：`src/node/hub_client.py` 的 `sync_documents()` 有 `TODO`，扫描后仅打印、未通过 HTTP 上传到 Hub——远端文档实际无法进入 Hub 索引
2. **`doc_response` 未转发**：Hub 的 `handle_node_message` 对 `doc_response` 直接返回 `None`，注释中的"转发给请求者"未实现；API 层也没有发送 `doc_request` 的端点
3. **`app_version` 仍为 `0.1.0`**（`config.py`），与实际交付版本不符
4. **认证未启用**：`nodes` 表有 `token` 字段，但注册与所有 API 均不校验
5. **无自动化测试**：仅 `tests/test_smoke.py`
6. **搜索为 ILIKE 全表扫描**：无全文索引，数据量大时性能受限
7. **分块参数未接线**：`config.py` 定义了 `chunk_size`（500）与 `chunk_overlap`（50），但 `vector_store.add_document` 硬编码 `chunk_size=500` 且不传 `chunk_overlap`——`AV_CHUNK_SIZE`/`AV_CHUNK_OVERLAP` 环境变量实际不生效

## Risks / Trade-offs

- **代码阅读可能遗漏隐含行为** → 每份规格写完后执行对照校验任务（见 tasks.md 第 1 节），逐能力复核
- **基线规格可能再次过时** → 恢复 spec-driven 流程后，所有后续改动强制走 propose → apply → sync；本变更归档时把该约定写入总结
- **中文需求描述与非中文工具链的兼容性** → OpenSpec 校验只检查结构（`### Requirement:` / `#### Scenario:`），描述语言不影响校验

## Migration Plan

1. 本变更目录内的 8 份 delta specs 即交付物（specs 阶段产出）
2. `/opsx:apply` 执行 tasks.md：逐能力对照代码校验，修正偏差
3. `/opsx:sync` 将 delta 合并为 `openspec/specs/<capability>/spec.md` 主规格
4. `openspec validate --strict` 确认主规格合法
5. `/opsx:archive` 归档本变更

## Open Questions

（无——能力切分与语言约定已定；如校验中发现代码行为与本设计冲突，以代码为准并修订规格）
