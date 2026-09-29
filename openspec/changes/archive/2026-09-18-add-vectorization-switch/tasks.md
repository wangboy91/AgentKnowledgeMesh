# Tasks: add-vectorization-switch

## 1. 设置与状态策略

- [x] 1.1 `services/rag/sync.py`:新增 `DEFAULT_VECTORIZATION_ENABLED = False`、`get_vectorization_enabled(session)` / `set_vectorization_enabled(session, bool)`(复用 `app_settings`);`DEFAULT_RAG_MODE` 由 `auto` 改为 `manual`
- [x] 1.2 同文件新增状态策略 `initial_rag_status(rag_mode, vectorization_enabled)`、`resolve_rag_status(...)`(excluded 粘性)与 `should_auto_index(...)`,并在模块 docstring 写明四态语义(`not_indexed` / `pending` / `indexed` / `excluded`)
- [x] 1.3 `api/settings.py`:`GET` 返回 `{rag_sync_mode, vectorization_enabled}`;`PUT` 支持部分更新(两项均可选、至少一项,非法值 400);开启方向先 `init_table()`(线程池)成功才落库,失败 500 且保持关闭;由 manual→auto 或开启开关使最终为「开启+auto」时后台补齐

## 2. 入库通道接入策略

- [x] 2.1 `services/indexer.py::sync_documents` 增加 `vectorization_enabled` 参数,初始状态改由 `resolve_rag_status` 决定,仅 `should_auto_index` 时构建向量载荷(excluded 文档不再被内容变更拉回)
- [x] 2.2 `api/nodes.py::_sync_node_documents` 同样接入(节点上传通道);删除清理逻辑不受开关影响
- [x] 2.3 `api/documents.py`:创建/更新文档按策略设定状态(并在 commit 后 `refresh`,修复 `updated_at` 过期导致的序列化失败);`scan` 读取两项设置后传入 indexer
- [x] 2.4 `main.py`:启动读设置,关闭时跳过 `init_table()` 并打印提示(开启时行为不变)

## 3. 检索与手动向量化端点

- [x] 3.1 `api/rag.py::/search`、`/context`:关闭时降级为关键词检索并返回同形响应(带 `"mode": "keyword"`);开启时行为不变
- [x] 3.2 `api/rag.py::/index`:关闭时 409;开启时纳入所有非 `excluded` 且有内容的文档,后台派发(带 pending 回写 `indexed`),响应 `{message, queued}`;不在请求路径上查向量库(分块总数由 `/stats` 提供)
- [x] 3.3 `api/rag.py::/stats`:返回 `vectorization_enabled`;关闭时不连向量库(`total_chunks` 为 0),开启时 `get_stats()` 走线程池
- [x] 3.4 `api/documents.py`:`PUT /{id}/rag` 与 `POST /rag/batch` 在关闭时 `enabled=true` 返回 409,`enabled=false` 放行
- [x] 3.5 `services/mcp_server.py::_search_documents(mode=semantic)`:关闭时降级为关键词检索,文本首行标注"向量化未开启"

## 4. Web UI

- [x] 4.1 `api/client.ts`:`Document.rag_status` 增加 `not_indexed`;`SettingsResponse` 含两项;新增 `setVectorization`;`RagIndexResponse` 改为 `{message, queued}`
- [x] 4.2 `pages/Settings.tsx`:新增「向量化」总开关(开启需确认);关闭时 RAG 模式区给出提示
- [x] 4.3 `components/FileTree.tsx` / `components/MarkdownViewer.tsx`:状态映射与筛选增加 `not_indexed`;`canPick` 与 `toggleRag` 的加入/移出判断按四态修正
- [x] 4.4 `pages/Knowledge.tsx` 单篇按钮文案判断、`pages/Dashboard.tsx` 索引结果展示(`queued`)同步
- [x] 4.5 `i18n/{zh,en}.ts`:新增开关/状态/降级提示文案(中英对齐,无硬编码)

## 5. 测试与验证

- [x] 5.1 更新 `tests/test_rag_modes.py`(默认 manual + 向量化关闭、补齐语义、全量索引纳入 not_indexed)与 `tests/test_node_sync.py`(显式开启向量化+auto)
- [x] 5.2 新增 `tests/test_vectorization_switch.py`:默认关闭;关闭时 scan/创建/更新/节点上传 → `not_indexed` 且无向量操作;开启时 `rag/index` 纳入 not_indexed 并回写 indexed;关闭时 `rag/index` 与「加入 RAG」409、「移出」放行;关闭时语义检索/上下文走关键词(不触向量库);`/rag/stats` 带 `vectorization_enabled` 且不连库;excluded 粘性
- [x] 5.3 `cd src/server && pytest` 全绿(112 项中 111 通过;`test_auth_matrix.py::test_ws_register_token_required` 为**改动前即存在**的环境性失败,已用原始 main.py 复现确认);`cd src/web && npm run build` 通过
- [x] 5.4 API 冒烟(SQLite 模式临时 Hub,2026-09-28 实测 10 项全过):默认态 `{rag_sync_mode: manual, vectorization_enabled: false}`;关闭时 `POST /api/rag/index` 409;`/api/rag/search` 与 `/api/rag/context` 返回 `mode: "keyword"`;`/api/rag/stats` 200 且不连向量库;`scan` 后新文档 `not_indexed`;`PUT /api/settings {vectorization_enabled:true}` 在无 pgvector 时 500 且**不落库**;文档级「加入 RAG」与批量加入 409、「移出」放行并转 `excluded`;改内容重扫后 `excluded` 保持(粘性)
- [ ] 5.5 API 冒烟(需 pgvector 部署,待用户环境确认):开启总开关成功后 `POST /api/rag/index` 回写 `indexed`、`/api/rag/search` 从 keyword 切回语义检索。本机 `src/server/.env` 指向远端 PG(`124.222.52.252`),未在用户远端库上执行

## 6. 文档与收尾

- [x] 6.1 `README.md` 使用说明:向量化默认关闭、开启方式、手动向量化入口
- [x] 6.2 `docs/api-reference.md`:`/api/settings` 两项设置、`/api/rag/index` 契约变更、检索降级与 `rag_status` 四态说明
- [x] 6.3 `src/server/.env.example` §4 注明向量化默认关闭、需在设置页开启;`docs/deployment.md`、`docs/search-engine-design.md`、`deploy/*.yml` 注释同步
- [x] 6.4 红线自查 + 完成报告(改动清单、验证结果、遗留项)
