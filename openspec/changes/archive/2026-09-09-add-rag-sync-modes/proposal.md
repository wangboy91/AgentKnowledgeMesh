# Proposal: add-rag-sync-modes

## Why

当前"哪些文档进向量库"不可控:节点文档上传即自动向量化、本地扫描需手动全量重建,粒度只有全量;用户需要"不是所有文档都进 RAG"的控制能力(如个人笔记不入库、精选文档才参与语义检索)。

## What Changes

- 新增全局设置 `rag_sync_mode`(`auto` / `manual`,默认 `auto`),持久化于 `app_settings` 表,提供 `GET/PUT /api/settings` 读写(admin 可写)
- 新增文档级 RAG 状态 `rag_status`(`indexed` / `pending` / `excluded`;存量迁移为 `indexed` 保持现状可检索)
- auto 模式:节点上传与**本地扫描**产生的新/变更文档自动进入后台向量化(补齐现状缺口:本地扫描自动);manual 模式:一切新文档默认 `excluded`,仅显式操作才入向量库
- 新增文档级操作:`PUT /api/documents/{id}/rag`(单篇加入/移出)与 `POST /api/documents/rag/batch`(批量);移出时删除该文档向量分块
- `POST /api/rag/index` 全量重建尊重 `excluded`(跳过);语义检索/上下文仅召回 `indexed`
- 文档列表/详情返回 `rag_status`,列表支持 `?rag_status=` 过滤
- Web:设置页 RAG 模式开关;文档列表状态列与单篇/批量加入/移出操作

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `vector-search`: 新增 RAG 同步模式与文档级勾选需求;语义检索仅召回 indexed;全量索引跳过 excluded
- `knowledge-indexing`: auto 模式下扫描触发后台向量同步
- `document-management`: 文档列表/详情携带 rag_status 并支持过滤

## Impact

- **server**:`app_settings` 模型与设置 API;`documents.rag_status` 列(存量迁移默认 indexed);抽取 `services/rag/sync.py` 统一索引通道(nodes 上传通道与本地扫描通道共用);search/index 端点按状态过滤
- **web**:设置页开关、文档列表列与批量操作
- **兼容**:默认 auto,行为与现状等价(节点自动、本地从"不自动"变为"自动"是行为增强,需在发布说明标注);存量向量数据不变
