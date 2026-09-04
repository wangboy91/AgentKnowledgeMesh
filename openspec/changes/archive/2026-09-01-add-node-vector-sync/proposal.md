# Proposal: add-node-vector-sync

## Why

节点经 `PUT /api/nodes/{node_id}/documents` 推送的文档只写入 documents 表，从不进入向量索引：本地扫描的文档可被语义检索，节点推送的文档不能。`vector-search` spec 的返回结构与过滤参数早已包含 `node_id`，但节点文档实际从未入库向量表——能力在 spec 层承诺了、实现从未接上。

## What Changes

- **Hub 侧嵌入**：节点文档的向量生成由 Hub 在接收推送后完成（而非节点端计算推送）。理由：混合检索的 sparse 侧（pg_trgm）建立在向量表 content 列上，Hub 必须持有全文，节点端计算嵌入只能省嵌入调用、省不了传输，却要付协议版本化与分块逻辑一致性的持续成本。
- **异步嵌入**：文档入库成功后向量生成在后台执行，`PUT /api/nodes/{node_id}/documents` 不因嵌入耗时阻塞响应（首次全量推送可能以分钟计）。
- **严格增量**：仅对本次同步中 created/updated（SHA256 哈希变化）的文档生成向量；哈希未变的文档绝不重新嵌入。删除的文档同步清理其向量。删除-重插的幂等语义由 `vector_store.add_document` 现有行为保证。
- **存量回填**：一次性迁移脚本为已入库但向量缺失的节点文档补建向量，只处理向量表中不存在的文档，不对已向量化的文档（如本地文档）重复嵌入。`POST /api/rag/index` 已覆盖全文档全量索引，回填脚本与它的区别正是「只补缺、不全量」。
- **降级不阻塞**：向量操作失败仅记录告警，文档同步照常成功（与现有 `RAG Graceful Degradation` 及文档生命周期同步的尽力而为语义一致）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `multi-node-sync`：`Hub Node Document Ingestion` 要求扩展——增量入库的同时维护向量索引（created/updated 异步嵌入、deleted 清理向量、失败降级不阻塞同步响应）。
- `vector-search`：`Vector Index Management` 的「文档生命周期同步」场景扩展——向量索引维护的触发路径纳入节点文档推送；新增「仅补缺失向量」的回填行为要求。

## Impact

- **代码**：
  - `src/server/app/api/nodes.py`：`_sync_node_documents` 在 commit 后按增量结果派发向量操作（需在删除前捕获待删文档的 doc_id，flush 获取新文档 id）。
  - 异步执行机制（FastAPI BackgroundTasks 或 `asyncio.to_thread`，具体取舍见 design.md）。
  - `src/server/scripts/`：新增存量回填脚本。
- **API**：`PUT /api/nodes/{node_id}/documents` 响应行为不变（仍返回同步统计），向量生成转为后台进行；无 breaking change。
- **依赖**：无新依赖；嵌入仍走现有 `AKM_EMBEDDING_PROVIDER` 配置（默认 ark/doubao），首次回填与首次节点全量推送产生一次性嵌入 API 费用。
- **成本护栏**：每次同步的嵌入量 ∝ 本次变化量（哈希比对既有逻辑），与库的总大小无关。
