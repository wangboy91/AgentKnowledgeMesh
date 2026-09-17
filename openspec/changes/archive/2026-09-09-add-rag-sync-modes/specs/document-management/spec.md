# document-management 能力增量(RAG 状态展示)

## ADDED Requirements

### Requirement: Document RAG Status Visibility
文档列表与详情 SHALL 携带 `rag_status` 字段;文档列表 SHALL 支持按 `rag_status` 过滤(`GET /api/documents?rag_status=excluded` 等)。

#### Scenario: 列表携带状态
- **WHEN** 客户端调用 `GET /api/documents`
- **THEN** 每项包含 `rag_status` 字段

#### Scenario: 按状态过滤
- **WHEN** 客户端调用 `GET /api/documents?rag_status=excluded`
- **THEN** 仅返回 `rag_status` 为 `excluded` 的文档
