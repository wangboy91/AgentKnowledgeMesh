# knowledge-indexing 能力增量

## MODIFIED Requirements

### Requirement: Scan Trigger API
系统 SHALL 提供 `POST /api/documents/scan` 端点,触发全量扫描与增量索引同步;**扫描入库的初始 RAG 状态 SHALL 由「向量化总开关 + `rag_sync_mode`」共同决定:仅当总开关开启且模式为 `auto` 时新/变更文档置 `indexed` 并在响应后派发后台向量同步,其余情况置 `not_indexed` 且 SHALL NOT 产生任何向量操作。**

#### Scenario: 扫描完成返回统计
- **WHEN** 客户端调用 `POST /api/documents/scan`
- **THEN** 系统执行扫描与同步,返回 `{"message": "Scan completed", "created": N, "updated": N, "deleted": N}`

#### Scenario: auto 模式扫描后自动向量化
- **WHEN** 向量化总开关为开启、RAG 模式为 `auto`,且本次扫描产生了 created/updated 文档
- **THEN** 系统在返回统计后,于后台对新/变更文档分块、嵌入并写入向量表(向量失败仅告警),文档状态为 `indexed`

#### Scenario: manual 模式扫描不产生向量
- **WHEN** RAG 模式为 `manual` 且本次扫描产生了 created/updated 文档
- **THEN** 这些文档 `rag_status` 为 `not_indexed`,无任何向量操作

#### Scenario: 向量化关闭时扫描不产生向量
- **WHEN** 向量化总开关为关闭(无论 RAG 模式为何)且本次扫描产生了 created/updated 文档
- **THEN** 这些文档 `rag_status` 为 `not_indexed`,无任何向量操作,也不初始化向量库

#### Scenario: 删除文档仍清理向量
- **WHEN** 本次扫描发现已消失的文档
- **THEN** 系统删除其索引记录,并在向量化开启时尽力清理其向量分块(关闭时向量库不可达,清理失败仅告警)
