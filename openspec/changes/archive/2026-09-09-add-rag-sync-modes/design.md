# Design: add-rag-sync-modes

## Context

现状:节点上传通道在 `_sync_node_documents` 后经 `_sync_vectors` 后台增量维护向量;本地扫描通道(`POST /api/documents/scan` → `sync_documents`)只写文档表;`POST /api/rag/index` 为全量重建;无任何模式/状态控制。方案详见 [docs/technical-design.md](../../../docs/technical-design.md) §5。

## Goals / Non-Goals

**Goals:**
- 全局 auto/manual 开关(运行时可切,持久化)
- 文档级勾选(excluded 文档绝不参与语义检索)
- 两条入库通道(节点上传、本地扫描)行为统一,共用一个索引服务

**Non-Goals:**
- 节点级/目录级模式粒度(YAGNI,先文档级)
- 关键词搜索的状态过滤(关键词搜全部文档,不受 rag_status 影响;仅语义检索受控)
- 向量数据的按模式分区

## Decisions

1. **设置存储用 `app_settings` KV 表**(key/value 文本)而非新配置项:运行时可变、免重启、Web 可改;`AKM_` 环境变量仅保留静态初始化默认值。
2. **`rag_status` 三态**(`pending`/`indexed`/`excluded`)而非布尔:向量化是异步后台过程,`pending` 使 UI 可展示"排队中";存量迁移默认 `indexed` 保持现状可检索。
3. **抽取 `services/rag/sync.py` 统一索引通道**:`index_documents(doc_ids)` / `remove_documents(doc_ids)`,nodes 上传、本地扫描、文档 API、勾选操作全部经由它,消灭 nodes.py 内嵌的 `_sync_vectors` 私有实现。
4. **模式切换语义**:切 manual 不清向量(只影响增量行为);切 auto 对非 excluded 补齐(后台);避免破坏性副作用。
5. **检索侧过滤在召回阶段完成**:关键词侧候选与向量侧查询均限定 `doc_id ∈ indexed 集合`(向量表按 doc_id 删除已实现,关键词侧 SQL 加过滤),而非结果后过滤,保证 limit 不被 excluded 挤占。

## Risks / Trade-offs

- [切回 auto 的补齐量大(万级文档)] → 后台执行 + 复用全量索引的去重逻辑;响应立即返回
- [关键词与语义结果集不一致造成困惑] → UI 在文档条目上明示"未入 RAG"徽标;文档说明两者边界
- [与 add-account-auth 并行时的鉴权叠加] → settings/勾选端点按 admin 矩阵落,变更间无耦合

## Migration Plan

1. `create_all` 建 `app_settings`;`documents` 加列(SQLite `ALTER TABLE ... ADD COLUMN` / PG 同),存量 `UPDATE` 为 `indexed`
2. 默认 auto → 行为与现状等价(本地扫描从"不自动"变"自动"为增强,发布说明标注)
3. 回滚:回退代码;`rag_status`/`app_settings` 列表残留无害

## Open Questions

无。
