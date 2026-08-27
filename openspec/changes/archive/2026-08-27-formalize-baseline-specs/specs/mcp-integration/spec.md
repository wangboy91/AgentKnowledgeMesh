## ADDED Requirements

### Requirement: MCP Server Transports
系统 SHALL 以 Model Context Protocol（MCP）Server 形式暴露知识库能力，支持 SSE 与 stdio 两种传输。

#### Scenario: SSE 传输连接
- **WHEN** MCP 客户端（Claude Code、Cursor 等）连接 `GET /api/mcp/sse`
- **THEN** 系统建立 Server-Sent Events 长连接，客户端请求经 `POST /api/mcp/messages` 送达，服务器推送经 SSE 流返回

#### Scenario: stdio 传输
- **WHEN** 以 stdio 模式启动 MCP Server
- **THEN** 系统通过标准输入/输出流提供同一套工具

### Requirement: Search Documents Tool
MCP Server SHALL 提供 `search_documents` 工具，参数为必填 `query` 与可选 `limit`（默认 5）。

#### Scenario: 搜索命中
- **WHEN** Agent 调用 `search_documents` 且关键词命中标题、路径或正文
- **THEN** 工具返回标题命中文档优先的列表，每篇含标题、路径、节点、大小（KB）、更新时间

#### Scenario: 搜索无结果
- **WHEN** 关键词无任何命中
- **THEN** 工具返回 "未找到与 '<关键词>' 相关的文档。"

### Requirement: Get Document Tool
MCP Server SHALL 提供 `get_document` 工具，参数为必填 `document_id`。

#### Scenario: 获取存在的文档
- **WHEN** Agent 调用 `get_document` 传入存在的文档 ID
- **THEN** 工具返回 Markdown 格式结果：标题、路径、节点、大小、更新时间与完整正文

#### Scenario: 文档不存在
- **WHEN** 传入不存在的文档 ID
- **THEN** 工具返回 "文档 ID <id> 不存在。"

### Requirement: List Documents Tool
MCP Server SHALL 提供 `list_documents` 工具，参数为可选 `node_id` 与 `limit`（默认 20），按更新时间倒序列出文档。

#### Scenario: 列出文档
- **WHEN** Agent 调用 `list_documents`
- **THEN** 工具返回形如 "- [id] 标题 (路径)" 的文档列表

#### Scenario: 按节点过滤
- **WHEN** Agent 传入 `node_id`
- **THEN** 仅列出该节点的文档

#### Scenario: 知识库为空
- **WHEN** 无任何文档
- **THEN** 工具返回 "暂无文档。"

### Requirement: Unknown Tool Rejection
MCP Server SHALL 拒绝未知工具调用。

#### Scenario: 调用不存在的工具
- **WHEN** Agent 调用未注册的工具名
- **THEN** 系统抛出 "Unknown tool: <名称>" 错误
