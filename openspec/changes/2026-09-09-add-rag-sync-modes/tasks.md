# Tasks: add-rag-sync-modes

## 1. 数据模型与设置

- [ ] 1.1 新增 `app/models/settings.py`(AppSetting:key 主键/value/updated_at)并导出;`documents` 模型加 `rag_status` 字段(默认 `indexed`);验证存量库迁移(启动建表 + SQLite 加列脚本)后 `uv run pytest` 全绿
- [ ] 1.2 新增 `app/api/settings.py`:`GET/PUT /api/settings`(读 viewer、写 admin);`rag_sync_mode` 合法值校验;curl 冒烟读写与默认值
- [ ] 1.3 模式切换语义:切 manual 不动向量;切 auto 后台补齐非 excluded;单测覆盖两种切换(`tests/test_rag_modes.py`)

## 2. 统一索引通道

- [ ] 2.1 新增 `services/rag/sync.py`:`index_documents(doc_ids)`(分块→嵌入→覆盖写入→状态转 indexed)与 `remove_documents(doc_ids)`(删分块→状态转 excluded);失败仅告警
- [ ] 2.2 nodes 上传通道切换到统一通道(删除 `_sync_vectors` 私有实现,行为不变回归 `tests/test_node_sync.py`);文档 API 创建/更新/删除路径接入
- [ ] 2.3 本地扫描通道接入:scan 后 auto 模式对 created/updated 派发后台索引;manual 模式置 excluded 且无向量操作;单测覆盖两模式

## 3. 检索与全量索引尊重状态

- [ ] 3.1 `POST /api/rag/index` 跳过 excluded;`GET /api/rag/search` 与 `/api/rag/context` 仅召回 indexed(关键词侧候选 SQL 过滤 + 向量侧 doc 集合过滤);单测:excluded 文档语义不可见、关键词可见
- [ ] 3.2 勾选端点:`PUT /api/documents/{id}/rag`、`POST /api/documents/rag/batch`(admin);加入 → pending→后台→indexed,移出 → excluded+删向量;单测覆盖状态机
- [ ] 3.3 文档列表/详情带 `rag_status`,`?rag_status=` 过滤;curl 验证

## 4. Web UI

- [ ] 4.1 设置页:RAG 模式开关(auto/manual)与说明文案;`client.ts` 增 settings API
- [ ] 4.2 文档列表:状态列(indexed/pending/excluded 徽标)、单篇加入/移出操作、勾选批量操作;`npm run build` 通过

## 5. 验证与收尾

- [ ] 5.1 E2E 手册:manual 下新增节点文档 → 语义不可见 → 勾选加入 → 语义命中 → 移出 → 不可见;auto 下扫描即命中
- [ ] 5.2 `uv run pytest` 全量回归;README/docs 发布说明(本地扫描 auto 行为增强);openspec verify
