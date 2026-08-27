## Why

AgentKnowledgeMesh 的 V0.1–V0.3 功能已全部实现并交付，但旧的 openspec 文档是自由格式（非 spec-driven），且内容已严重过时（缺少 Context API、MCP、RAG、文档转换等端点；路径仍指向重构前的 `server/`），已在 2026-08-27 的仓库重组中删除并归档。新初始化的 `openspec/`（spec-driven schema）目前是空的——没有主规格（main specs）描述系统的真实现状。

在开始任何新工作（V1.0 知识图谱、补测试等）之前，需要先把已交付的能力固化为正式的 spec-driven 基线规格，作为后续所有变更的对照基准。

## What Changes

- 为已实现的 8 项能力创建基线规格（全部为 `## ADDED Requirements`，因为 `openspec/specs/` 目前为空）
- 规格内容以**现有代码为准**（`src/server/app/api/`、`src/server/app/services/`、`src/node/`），归档的旧文档（`openspec/changes/archive/2026-08-27-legacy-design-docs/`）仅作背景参考
- 纯文档变更：**不修改任何代码**、API、依赖或数据库结构
- 完成后通过 `/opsx:sync` 将 delta specs 合并为 `openspec/specs/<capability>/spec.md` 主规格

## Capabilities

### New Capabilities

- `knowledge-indexing`: Markdown 递归扫描与增量索引——目录扫描规则、SHA256 哈希变更检测、SQLite/PostgreSQL 可切换存储、`/api/documents/scan` 触发
- `document-management`: 文档管理 REST API——列表、文件树、详情、更新（在线编辑保存）
- `keyword-search`: 关键词搜索——基于 SQL LIKE 的标题/路径/全文检索，标题匹配优先，可配置结果上限
- `multi-node-sync`: Hub + Node 分布式同步——WebSocket 消息协议（register/heartbeat/doc_update/sync_request/doc_request/doc_response）、节点注册与心跳、节点管理 API
- `agent-context-api`: Agent 上下文接口——`GET /api/context`，为 AI Agent 返回适配 prompt 注入的相关文档
- `mcp-integration`: MCP Server 集成——通过 SSE 暴露 Model Context Protocol 工具，供 Claude Code / Codex 等调用
- `vector-search`: 向量语义搜索（RAG）——嵌入索引、语义检索端点（`/api/rag`）
- `document-conversion`: 文档转换——PDF/Word/HTML/URL → Markdown，含文件上传转换

### Modified Capabilities

（无——`openspec/specs/` 目前为空，所有能力均为首次建立基线）

## Impact

- **新增**：`openspec/specs/` 下 8 个能力的主规格（sync 之后）；本变更目录下对应的 8 份 delta specs
- **代码/API/依赖**：零变更——本变更只产出规格文档，描述的是已存在的系统行为
- **文档**：归档于 `openspec/changes/archive/2026-08-27-legacy-design-docs/` 的旧设计文档将被正式的主规格取代（保留作历史参考）
- **后续工作基准**：V1.0 知识图谱、补充测试覆盖等后续变更将以这套基线规格为对照
