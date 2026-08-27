## ADDED Requirements

### Requirement: Keyword Search Endpoint
系统 SHALL 提供 `GET /api/search` 端点，基于不区分大小写的模糊匹配（ILIKE）在文档标题、路径和正文中搜索关键词。

#### Scenario: 关键词命中
- **WHEN** 客户端调用 `GET /api/search?q=<关键词>`
- **THEN** 系统返回 `{"query": <关键词>, "count": N, "documents": [...]}`，documents 为元信息列表（不含正文），仅包含标题、路径或正文命中关键词的文档

#### Scenario: 缺少关键词
- **WHEN** 请求未提供 `q` 参数或为空字符串
- **THEN** 系统返回 422 参数校验错误

#### Scenario: 结果数量上限
- **WHEN** 客户端提供 `limit` 参数
- **THEN** 系统在 1–100 范围内接受该值（默认 20），超出范围返回校验错误

### Requirement: Title-Priority Ranking
搜索结果 SHALL 优先展示标题匹配的文档，同级内按更新时间倒序。

#### Scenario: 标题匹配优先于正文匹配
- **WHEN** 关键词同时命中文档 A 的标题和文档 B 的正文
- **THEN** 文档 A 排在文档 B 之前

#### Scenario: 同级按更新时间排序
- **WHEN** 多个文档的标题匹配情况相同
- **THEN** 按 `updated_at` 倒序排列
