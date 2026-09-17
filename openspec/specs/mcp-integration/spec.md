# mcp-integration 能力规格

## Purpose

以 MCP（Model Context Protocol）Server 形式暴露知识库能力，让 Claude Code、Cursor 等 AI 工具通过标准工具接口搜索与读取文档。

## Requirements

### Requirement: MCP Server Transports
系统 SHALL 以 Model Context Protocol(MCP)Server 形式暴露知识库能力,支持三种接入形态:Hub SSE(`GET /api/mcp/sse`)、Hub stdio(`akm-hub --mcp`,本机信任)与**节点本地 stdio 代理**(`akm-node --mcp`,智能体拉起子进程,经节点凭证转发 Hub HTTP API)。三种形态 SHALL 提供同一套工具。

#### Scenario: SSE 传输连接
- **WHEN** MCP 客户端(Claude Code、Cursor 等)连接 `GET /api/mcp/sse`
- **THEN** 系统建立 Server-Sent Events 长连接,客户端请求经 `POST /api/mcp/messages` 送达,服务器推送经 SSE 流返回

#### Scenario: stdio 传输
- **WHEN** 以 stdio 模式启动 Hub 的 MCP Server
- **THEN** 系统通过标准输入/输出流提供同一套工具

#### Scenario: 节点本地代理传输
- **WHEN** 智能体以 `uv run akm-node --mcp` 作为 MCP 命令拉起子进程
- **THEN** 子进程以 stdio 提供与 Hub 一致的工具,工具调用经 HTTP 转发至 Hub 并回传结果

#### Scenario: 未登录节点的 MCP 模式
- **WHEN** 节点本地无有效凭证(未执行过 `akm-node login`)时启动 `akm-node --mcp`
- **THEN** 进程输出引导信息"请先执行 akm-node login"并以非零码退出

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

### Requirement: Node Local MCP Proxy Behavior
节点本地 MCP 代理 SHALL 将工具调用转调 Hub HTTP API 并携带节点凭证:`search_documents` → `GET /api/search`(支持可选语义模式)、`get_document` → `GET /api/documents/{id}`、`list_documents` → `GET /api/documents`;Hub 不可达或返回鉴权失败时,SHALL 返回包含原因的明确错误信息,而非崩溃或挂起。

#### Scenario: 经代理搜索
- **WHEN** 智能体对节点代理调用 `search_documents`
- **THEN** 代理携带节点凭证请求 Hub 搜索端点,返回与 Hub MCP 一致格式的结果

#### Scenario: Hub 不可达
- **WHEN** 节点代理无法连接 Hub
- **THEN** 工具返回 "无法连接 Hub(<地址>):请检查 Hub 状态" 类错误信息,进程保持可用

#### Scenario: 凭证失效
- **WHEN** Hub 对节点凭证返回 401
- **THEN** 工具返回 "节点凭证已失效,请重新执行 akm-node login" 类错误信息

#### Scenario: 检索质量由 Hub 保证
- **WHEN** 任意接入形态执行语义相关查询
- **THEN** 语义检索能力仅由 Hub 提供,节点代理不实现本地向量检索
