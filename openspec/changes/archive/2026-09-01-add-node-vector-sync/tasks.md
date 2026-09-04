# Tasks: add-node-vector-sync

## 1. 同步路径向量维护（nodes.py）

- [x] 1.1 重构 `_sync_node_documents`：commit 前捕获增量数据（flush 获取新文档 id、删除前查询待删 doc_id），返回统计与向量操作载荷；验证现有测试 `test_node_sync.py` 全部通过（行为不变）
- [x] 1.2 `PUT /api/nodes/{node_id}/documents` 注入 BackgroundTasks，commit 成功后派发同步后台函数（线程池执行、逐文档 try/except 记 warning）；验证：推送含新文档的请求即时返回统计，后台向量写入完成（测试中 monkeypatch vector_store 断言调用）
- [x] 1.3 在测试中覆盖增量语义：created/updated 文档触发 `add_document`、哈希未变文档不触发、deleted 文档触发 `delete_document`；验证 `test_node_sync.py` 新增用例通过
- [x] 1.4 删除节点级联清理向量：`DELETE /api/nodes/{node_id}` 删除文档前捕获 doc_id，删除后清理向量，失败仅告警；验证新增测试用例通过

## 2. 回填脚本与 vector_store 辅助接口

- [x] 2.1 vector_store 新增 `get_indexed_doc_ids() -> set[int]`（SELECT DISTINCT doc_id）；验证单元测试（可参照 `test_vector_store.py` 既有风格，跳过无 PG 环境时）
- [x] 2.2 新增 `src/server/scripts/backfill_node_vectors.py`：差集计算只补缺失向量、逐文档失败降级、输出补建/跳过/失败统计（风格对齐 `migrate_sqlite_to_pg.py`）；验证：脚本 `--help` 可运行，且在有 PG 的环境下手工执行一次输出统计（注：本机无运行中的 PG，已验证 `--help` 与无库/无 PG 的优雅降级路径，真实回填待部署环境执行）

## 3. 集成验证

- [x] 3.1 运行 server 全量测试（`uv run pytest`），确认无回归（31/31 通过；注：需 `uv run --extra dev pytest`，dev 依赖在 optional-dependencies 中）
- [ ] 3.2 端到端手工验证（可选，需 PG + 嵌入配置）：节点推送文档 -> `/api/rag/search` 能检索到节点文档；删除节点后搜索不再命中其内容
