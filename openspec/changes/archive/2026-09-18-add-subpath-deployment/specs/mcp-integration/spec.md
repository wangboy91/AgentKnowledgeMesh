# mcp-integration 能力增量(SSE 通告端点修正)

## MODIFIED Requirements

### Requirement: MCP Server Transports
系统 SHALL 以 Model Context Protocol(MCP)Server 形式暴露知识库能力,支持三种接入形态:Hub SSE(`GET /api/mcp/sse`)、Hub stdio(`akm-hub --mcp`,本机信任)与**节点本地 stdio 代理**(`akm-node --mcp`,智能体拉起子进程,经节点凭证转发 Hub HTTP API)。三种形态 SHALL 提供同一套工具。**SSE 形态 SHALL 向客户端通告实际可用的消息端点,并随部署前缀拼接。**

#### Scenario: SSE 传输连接
- **WHEN** MCP 客户端(Claude Code、Cursor 等)连接 `GET /api/mcp/sse`
- **THEN** 系统建立 Server-Sent Events 长连接,客户端请求经 `POST /api/mcp/messages` 送达,服务器推送经 SSE 流返回

#### Scenario: SSE 通告的消息端点可直接回发
- **WHEN** MCP 客户端按 SSE 流首帧通告的 endpoint 回发消息
- **THEN** 该地址即真实路由(根路径部署为 `/api/mcp/messages`;配置部署前缀时为 `{前缀}/api/mcp/messages`),请求被受理(202)而非 404

#### Scenario: stdio 传输
- **WHEN** 以 stdio 模式启动 Hub 的 MCP Server
- **THEN** 系统通过标准输入/输出流提供同一套工具

#### Scenario: 节点本地代理传输
- **WHEN** 智能体以 `uv run akm-node --mcp` 作为 MCP 命令拉起子进程
- **THEN** 子进程以 stdio 提供与 Hub 一致的工具,工具调用经 HTTP 转发至 Hub 并回传结果

#### Scenario: 未登录节点的 MCP 模式
- **WHEN** 节点本地无有效凭证(未执行过 `akm-node login`)时启动 `akm-node --mcp`
- **THEN** 进程输出引导信息"请先执行 akm-node login"并以非零码退出
