# Design: add-node-vector-sync

## Context

见 proposal.md 的 Why：节点推送文档只入 documents 表、不进向量索引。当前实现要点：

- `_sync_node_documents`（`src/server/app/api/nodes.py`）在 async 会话中按 (node_id, path) 增量同步，commit 后直接返回统计。
- `vector_store`（`src/server/app/services/rag/vector_store.py`）基于同步 psycopg2 连接：`add_document`（先删后插、幂等）与 `delete_document` 均为阻塞调用，内含嵌入 API 请求。
- `POST /api/rag/index` 已提供全量索引，但不区分"已有向量/缺失向量"。
- 诊断补充发现：`DELETE /api/nodes/{node_id}` 删除文档但不清理向量，会遗留孤儿分块（spec 已纳入级联清理要求）。

## Goals / Non-Goals

**Goals:**

- 节点文档推送后自动进入向量索引，嵌入在响应返回后的后台执行，不阻塞事件循环。
- 每次同步的嵌入量严格 ∝ 本次 created/updated 量。
- 提供只补缺的存量回填脚本。
- 向量失败不阻塞同步主流程。

**Non-Goals:**

- 不改动节点端（Node）代码与推送协议。
- 不实现 WebSocket `doc_update` 消息的落库（独立缺口，另行立项）。
- 不引入嵌入队列/重试调度等持久化任务机制（当前规模用进程内后台任务足够）。

## Decisions

### Decision 1: 后台执行用 FastAPI BackgroundTasks（同步函数）

`add_document`/`delete_document` 是同步阻塞调用（psycopg2 + 嵌入 API），直接在 async 端点中调用会阻塞事件循环。

- **选择**：`PUT /api/nodes/{node_id}/documents` 端点注入 `BackgroundTasks`，注册一个**同步 def** 的向量维护函数。FastAPI 对同步后台函数自动走线程池执行，响应先返回、嵌入后台进行。
- **备选**：`asyncio.to_thread` -- 需要自行管理任务创建与异常捕获，且与请求生命周期脱钩；BackgroundTasks 由 Starlette 托管异常日志，代码量更小。两者效果等价，取更简者。
- **注意**：后台函数内部不得触碰请求级的 `session`（响应后连接已归还）；只使用 vector_store 的接口 + 提前捕获好的文档数据（doc_id、title、path、content、node_id）。

### Decision 2: 在 commit 前捕获向量操作所需数据

- created 文档：commit 前调用 `await session.flush()` 使新 Document 获得 id，逐条记录 `(doc.id, title, path, content, node_id)`。
- updated 文档：更新后的字段本就在手上，直接记录。
- deleted 文档：bulk delete 执行**前**先查出 missing 路径对应的 `doc.id` 列表（bulk delete 后取不到）。
- 全部数据在 commit 成功后才派发后台任务，避免"事务回滚但向量已写"的不一致。

### Decision 3: 失败降级边界放在派发层

后台向量函数整体 try/except，逐文档捕获异常、记 warning 日志后继续处理下一篇（一篇失败不拖垮同批其余文档）；端点层不再捕获 -- 派发本身（构造任务参数）不会触发向量/嵌入调用。与 spec 的"嵌入失败降级"场景一致。

### Decision 4: 回填脚本独立于 API，复用 vector_store

新增 `src/server/scripts/backfill_node_vectors.py`（与既有 `migrate_sqlite_to_pg.py` 同级同风格）：

- vector_store 新增 `get_indexed_doc_ids() -> set[int]`（`SELECT DISTINCT doc_id`），这是"只补缺"判断的最小接口。
- 脚本查全部文档（可按 node_id 过滤），差集即待补文档，逐篇调用 `add_document`，统计补建/跳过/失败数量并打印。
- 不加 `--force`（全量重建已有 `POST /api/rag/index` 覆盖），避免两个入口语义重叠。

### Decision 5: 删除节点时级联清理向量

`DELETE /api/nodes/{node_id}` 在删除文档**前**查出该节点全部 `doc.id`，删除文档与节点记录后，逐 doc_id 调用 `delete_document`；清理失败仅记 warning、不影响删除响应（与尽力而为语义一致）。

## Risks / Trade-offs

- [首次全量推送分钟级嵌入、无进度可见] -> 后台任务逐文档记 info 日志（`Added N chunks for doc X` 已有 debug 级）；不做进度 API（Non-Goal，规模到了再立项）。
- [进程重启导致后台任务丢失，向量缺失且无重试] -> 由回填脚本兜底：任何时候怀疑缺失都可重跑（幂等、只补缺）。
- [BackgroundTasks 在测试中默认同步执行] -> 测试断言行为（向量已写入/已清理）而非异步性。
- [并发推送同一节点时先删后插的竞态] -> 与现状同风险级别（documents 表写入本身无锁）；向量侧 `add_document` 先删后插，最坏重复插入由主键 `doc_{id}_chunk_{i}` 冲突暴露，不做额外同步原语。

## Migration Plan

1. 部署新代码（无 schema 变更、无新依赖，直接滚动替换）。
2. 一次性运行 `python -m scripts.backfill_node_vectors`（server 目录下）为存量节点文档补向量。
3. 回滚：直接回退旧代码；已写入的向量对旧代码无害（旧代码不读不写 node 文档向量），需要时可 `DELETE FROM document_vectors WHERE node_id != 'local'` 手工清理。

## Open Questions

（无 -- 异步机制、数据捕获时机、回填形态均已定。）
