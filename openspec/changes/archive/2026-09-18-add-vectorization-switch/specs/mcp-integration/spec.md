# mcp-integration 能力增量

## MODIFIED Requirements

### Requirement: Search Documents Tool
MCP Server SHALL 提供 `search_documents` 工具，参数为必填 `query` 与可选 `mode`(`keyword` 默认 / `semantic`)、`limit`（默认 5）。**`mode=semantic` 且向量化总开关关闭时,系统 SHALL 降级为关键词检索并在结果文本中明示降级原因,而非报错。**

#### Scenario: 搜索命中
- **WHEN** Agent 调用 `search_documents` 且关键词命中标题、路径或正文
- **THEN** 工具返回标题命中文档优先的列表，每篇含标题、路径、节点、大小（KB）、更新时间

#### Scenario: 搜索无结果
- **WHEN** 关键词无任何命中
- **THEN** 工具返回 "未找到与 '<关键词>' 相关的文档。"

#### Scenario: 语义模式且向量化开启
- **WHEN** Agent 调用 `search_documents` 且 `mode=semantic`、向量化总开关开启
- **THEN** 工具执行混合向量检索,仅召回 `rag_status` 为 `indexed` 的文档

#### Scenario: 语义模式在向量化关闭时降级
- **WHEN** Agent 调用 `search_documents` 且 `mode=semantic`,但向量化总开关关闭
- **THEN** 工具改用关键词检索返回结果,并在文本首行标注"向量化未开启,已降级为关键词检索",不返回错误
