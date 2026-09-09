# knowledge-indexing 能力增量(RAG 同步模式联动)

## MODIFIED Requirements

### Requirement: Scan Trigger API
系统 SHALL 提供 `POST /api/documents/scan` 端点,触发全量扫描与增量索引同步;**auto 模式下,对本次产生的新增/更新文档 SHALL 在响应后派发后台向量同步;manual 模式下 SHALL NOT 产生任何向量操作。**

#### Scenario: 扫描完成返回统计
- **WHEN** 客户端调用 `POST /api/documents/scan`
- **THEN** 系统执行扫描与同步,返回 `{"message": "Scan completed", "created": N, "updated": N, "deleted": N}`

#### Scenario: auto 模式扫描后自动向量化
- **WHEN** RAG 模式为 `auto` 且本次扫描产生了 created/updated 文档
- **THEN** 系统在返回统计后,于后台对新/变更文档分块、嵌入并写入向量表(向量失败仅告警)

#### Scenario: manual 模式扫描不产生向量
- **WHEN** RAG 模式为 `manual` 且本次扫描产生了 created/updated 文档
- **THEN** 这些文档 `rag_status` 为 `excluded`,无任何向量操作
