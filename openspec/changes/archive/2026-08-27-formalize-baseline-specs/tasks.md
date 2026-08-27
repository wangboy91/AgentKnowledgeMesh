## 1. Delta Specs 对照代码校验

> 本变更为纯文档变更：8 份 delta specs 已在 specs/ 目录产出。本节逐能力核对规格描述与代码实际行为是否一致，发现偏差即修订规格（以代码为准）。

- [x] 1.1 校验 `knowledge-indexing`：对照 `services/scanner.py`（跳过规则、多目录前缀）、`services/indexer.py`（增量同步三态）、`config.py`（默认值）、`models/document.py`（字段与唯一约束）
- [x] 1.2 校验 `document-management`：对照 `api/documents.py`（列表/树/详情/创建/更新、409/404）、`api/__init__.py`（stats）、`main.py`（health、SPA 回退）
- [x] 1.3 校验 `keyword-search`：对照 `api/search.py`（ILIKE 范围、limit 1–100 默认 20、标题优先排序）
- [x] 1.4 校验 `multi-node-sync`：对照 `services/websocket.py`（注册/心跳/断线/4001）、`api/nodes.py`（五个端点）、`src/node/hub_client.py` 与 `src/node/config.py`（身份生成、30s 心跳、5s 重连）
- [x] 1.5 校验 `agent-context-api`：对照 `api/context.py`（limit 1–20 默认 5、node_id 过滤、返回全文字段）
- [x] 1.6 校验 `mcp-integration`：对照 `api/mcp.py`（SSE + messages 端点）、`services/mcp_server.py`（三个工具的参数默认值与返回文案、stdio 模式）
- [x] 1.7 校验 `vector-search`：对照 `api/rag.py`（search/context/index/stats 的降级行为）、`services/rag/vector_store.py`（懒初始化、维度检测、重建表、HNSW/halfvec）、`services/rag/embeddings.py` 与 `config.py`（供应商、分块参数）
- [x] 1.8 校验 `document-conversion`：对照 `api/convert.py`（支持格式、400/500、命名规则、临时文件清理）与 `services/converters/`

## 2. 同步与验收

- [x] 2.1 运行 `/opsx:sync` 将 8 份 delta specs 合并为 `openspec/specs/<capability>/spec.md` 主规格（新能力：创建文件并补 Purpose 与 Requirements 结构）
- [x] 2.2 运行 `openspec validate --strict` 确认主规格结构合法，修复报告的问题
- [x] 2.3 抽查一个主规格（如 `knowledge-indexing`）确认 ADDED 需求已完整落入且场景未丢失
- [x] 2.4 确认 `openspec list` 中本变更仍处于活跃状态、可进入归档流程
