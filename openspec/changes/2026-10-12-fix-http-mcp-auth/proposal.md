## Why

HTTP MCP 已通过 viewer 鉴权，但调用者没有传到写工具；SSE 会话未绑定应用凭证。需用隔离测试确认并封闭这一权限边界。

## What Changes

- SSE 与消息请求向 MCP 库传入已验证的凭证身份，绑定会话归属。
- HTTP 工具调用复用统一角色检查，viewer 禁止 create/update；Hub stdio 保持本机信任。
- 保留三个非敏感查询的结果和定向回归证据。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `mcp-integration`: 增加 HTTP 工具鉴权与会话归属要求。

## Impact

仅 Hub HTTP MCP、统一鉴权辅助函数、测试与接口文档。无新依赖、数据库迁移、索引或架构替换。viewer 过去可写的行为将被拒绝。
