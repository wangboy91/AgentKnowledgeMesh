## ADDED Requirements

### Requirement: Agent Context Query
系统 SHALL 提供 `GET /api/context` 端点，为 AI Agent 返回与查询相关的文档**完整内容**，以便直接注入 prompt。

#### Scenario: 查询相关文档
- **WHEN** Agent 调用 `GET /api/context?q=<关键词>`
- **THEN** 系统在标题、路径、正文中做不区分大小写的模糊匹配，返回 `{"query": ..., "count": N, "documents": [{"title", "content", "path", "node_id"}]}`，每篇文档包含全文

#### Scenario: 限制返回数量
- **WHEN** 请求携带 `limit` 参数
- **THEN** 系统在 1–20 范围内接受该值（默认 5）

#### Scenario: 按节点过滤
- **WHEN** 请求携带 `node_id` 参数
- **THEN** 仅返回该节点的文档

#### Scenario: 标题匹配优先
- **WHEN** 关键词同时命中标题与正文
- **THEN** 标题命中的文档优先返回，同级按 `updated_at` 倒序

#### Scenario: 缺少查询词
- **WHEN** 请求未提供 `q` 或为空
- **THEN** 系统返回 422 参数校验错误
