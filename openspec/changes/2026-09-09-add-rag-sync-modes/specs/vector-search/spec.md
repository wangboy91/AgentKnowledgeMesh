# vector-search 能力增量(RAG 同步模式)

## ADDED Requirements

### Requirement: RAG Sync Mode
系统 SHALL 维护全局设置 `rag_sync_mode`(`auto` 或 `manual`,默认 `auto`),持久化于应用设置存储并支持运行时切换;提供 `GET /api/settings`(viewer 可读)与 `PUT /api/settings`(仅 admin)。

#### Scenario: 默认自动模式
- **WHEN** 未配置 RAG 模式
- **THEN** 系统处于 `auto`:节点上传与本地扫描产生的新/变更文档自动进入后台向量化

#### Scenario: 切换为手动
- **WHEN** admin 将模式切换为 `manual`
- **THEN** 此后新文档(节点上传或本地扫描)默认标记为 `excluded`,不产生向量操作;既有向量**不**被清除

#### Scenario: 切回自动补齐索引
- **WHEN** admin 将模式从 `manual` 切回 `auto`
- **THEN** 系统将所有非 `excluded` 的文档补齐向量化(后台执行)

### Requirement: Document-Level RAG Selection
系统 SHALL 为每篇文档维护 RAG 状态 `rag_status`(`indexed` / `pending` / `excluded`),并提供单篇与批量操作(admin):`PUT /api/documents/{doc_id}/rag`(body `{"enabled": bool}`)与 `POST /api/documents/rag/batch`(body `{"doc_ids": [...], "enabled": bool}`)。

#### Scenario: 手动加入 RAG
- **WHEN** admin 对 `excluded` 文档执行"加入 RAG"(单篇或批量)
- **THEN** 该文档标记 `pending` 并后台向量化,完成后转 `indexed`

#### Scenario: 移出 RAG 清理向量
- **WHEN** admin 对某文档执行"移出 RAG"
- **THEN** 该文档标记 `excluded` 并删除其全部分块向量

#### Scenario: 非管理员被拒
- **WHEN** viewer 调用文档 RAG 勾选端点
- **THEN** 返回 403

## MODIFIED Requirements

### Requirement: Semantic Search Endpoint
系统 SHALL 提供 `GET /api/rag/search` 端点,基于向量相似度与关键词匹配进行混合检索,以 RRF 融合两侧结果,并返回满足相似度阈值的相关分块(同一文档可返回多个分块)。**检索 SHALL 仅召回 `rag_status` 为 `indexed` 的文档。**

#### Scenario: 语义检索
- **WHEN** 客户端调用 `GET /api/rag/search?q=<查询文本>`
- **THEN** 系统分别执行向量检索与关键词匹配,融合后按相关度排序返回 `{"query", "count", "results": [{"doc_id", "title", "path", "node_id", "chunk", "score"}]}`,limit 范围 1–20(默认 5),支持 `node_id` 过滤

#### Scenario: 同文档只保留最佳分块
- **WHEN** 同一文档的多个分块均与查询相关
- **THEN** 系统返回该文档的多个最佳分块(每文档有数量上限),而非仅保留一个分块

#### Scenario: 相似度阈值过滤
- **WHEN** 检索候选中存在相似度低于阈值的项
- **THEN** 系统不返回这些低于阈值的候选,而非无条件凑满 limit

#### Scenario: 关键词精确命中
- **WHEN** 查询包含文件名、ID 或专有名词等精确词项
- **THEN** 关键词匹配确保这些精确命中进入融合候选,弥补纯向量检索的漏检

#### Scenario: 排除文档不召回
- **WHEN** 某文档 `rag_status` 为 `excluded`(或尚未 `indexed`)
- **THEN** 无论其内容与查询多相关,均不出现在检索与 RAG 上下文结果中

#### Scenario: 检索失败降级
- **WHEN** 向量检索过程发生异常(如数据库不可用)
- **THEN** 系统返回 `{"query", "count": 0, "results": [], "error": <信息>}`,不抛出 500

### Requirement: Vector Index Management
系统 SHALL 提供 `POST /api/rag/index` 端点,将数据库中有内容的文档向量化入库(**`rag_status` 为 `excluded` 的文档 SHALL 被跳过**);auto 模式下文档增删改时 SHALL 尽力同步向量索引,触发路径包括文档 API 的创建/更新/删除、节点文档推送的增量入库与本地扫描的增量同步;manual 模式下仅显式勾选产生向量操作。

#### Scenario: 全量索引
- **WHEN** 客户端调用 `POST /api/rag/index`
- **THEN** 系统遍历除 `excluded` 外的全部文档,对每篇有内容的文档分块、嵌入并写入向量表,返回 `{"message", "indexed": N, "total_chunks": M}`

#### Scenario: 重复索引覆盖旧向量
- **WHEN** 对已索引文档再次入库
- **THEN** 系统先删除该文档的旧分块向量再写入新向量

#### Scenario: 文档生命周期同步
- **WHEN** auto 模式下文档经索引同步、文档 API 创建/更新/删除、节点文档推送或本地扫描被增量入库
- **THEN** 系统尽力同步向量索引(新增/覆盖/删除对应向量);向量操作失败仅记录告警,不影响主流程

#### Scenario: 手动模式无隐式向量操作
- **WHEN** manual 模式下节点上传或本地扫描产生新文档
- **THEN** 系统不入库向量,直到该文档被显式"加入 RAG"

#### Scenario: 索引失败降级
- **WHEN** 全量索引过程发生异常
- **THEN** 系统返回 `{"message": "Index failed: ...", "indexed": 0}`,不抛出 500
