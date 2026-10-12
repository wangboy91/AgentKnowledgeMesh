## Context

见 proposal.md。现有 MCP SDK 的 SSE 传输支持 scope user 的凭证归属检查，但应用只解析 Principal，未注入 SDK 身份。SDK 消息 metadata 将 HTTP Request 放入工具上下文。

## Goals / Non-Goals

Goals: 每次消息用当前角色，凭证绑定会话，隔离验证。
Non-Goals: 新模型、全库索引、Wiki、节点协议修改。

## Decisions

1. 将统一角色检查提取为 auth 辅助函数，REST 依赖与 MCP 共用。
2. HTTP 路由把已验证 Principal 放入 scope；工具从上下文 HTTP Request 取 Principal。HTTP 缺失身份必须拒绝，stdio 无 HTTP 请求维持信任。
3. 复用 SDK AuthenticatedUser 与 AccessToken 会话所有权，client_id 使用凭证 SHA256，避免明文凭证进入归属表；POST 同样注入。拒绝不同凭证复用会话。
4. 测试用 SQLite 内存库、进程内 ASGI，不启动监听服务；向量开关关闭，不访问付费模型。

## Risks / Trade-offs

- SDK 版本接口差异 → 以当前已安装源码为准并覆盖真实 SSE/POST 链路。
- 行为收紧 → viewer 写工具改为权限错误；端点与工具参数保持兼容。

## Migration Plan

无数据库迁移。发布不在本次授权范围内，所有改动留工作区。回退可撤销本次文件差异，不触碰用户原有文件。
