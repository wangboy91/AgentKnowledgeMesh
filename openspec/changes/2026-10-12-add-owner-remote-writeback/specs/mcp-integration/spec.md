## ADDED Requirements

### Requirement: Strict Owner Readonly MCP Barrier
系统 SHALL 在 owner-readonly-v1 下隔离 HTTP MCP，Hub stdio 工具清单 SHALL 为空且工具调用返回 isError；Node 本地正文 MCP SHALL 拒绝启动。未经核验的第三方正文客户端 MUST NOT 因 MCP 接入默认获得不落盘合规承诺。

#### Scenario: 严格模式第三方工具不返回正文
- **WHEN** profile 开启且 HTTP 或 stdio MCP 请求旧读写工具
- **THEN** HTTP 入口被拒，stdio 返回错误而无正文或保存成功，Node 代理不开放
