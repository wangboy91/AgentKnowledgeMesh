## ADDED Requirements

### Requirement: HTTP MCP Tool Authorization
HTTP MCP SHALL 在每次工具调用时使用消息请求当前已验证的身份；viewer 用户和 viewer API Token 的 create_document 与 update_document SHALL 返回明确的权限错误且不写入。admin SHALL 可以写入 local 文档。Hub stdio SHALL 保持本机信任语义。

#### Scenario: viewer 读写边界
- **WHEN** viewer 调用搜索和写工具
- **THEN** 搜索可用，写工具返回 isError 且数据库不变

#### Scenario: admin 写入
- **WHEN** admin 在自己的会话调用写工具
- **THEN** 写入成功并归属 local

#### Scenario: 会话中角色被降级
- **WHEN** admin 开启会话后其当前角色改为 viewer，再发送写调用
- **THEN** 写调用按 viewer 拒绝

#### Scenario: 本机 stdio
- **WHEN** Hub stdio 调用写工具
- **THEN** 保持本机信任写入

### Requirement: HTTP MCP Session Ownership
HTTP MCP SHALL 将 SSE 会话绑定到创建它的凭证；其他凭证向该会话发送消息 SHALL 返回 404，且不得执行工具。同一主体的新凭证也 SHALL 不能复用旧会话。会话断开 SHALL 释放归属状态。

#### Scenario: 跨凭证会话回发
- **WHEN** 另一用户、另一 API Token 或同一用户的新 JWT 向已有 SSE 会话发送消息
- **THEN** 返回 404，不向会话投递消息

#### Scenario: 同凭证会话回发
- **WHEN** 同一有效凭证向自己已建立的 SSE 会话发送消息
- **THEN** 受理消息

#### Scenario: 会话清理
- **WHEN** SSE 会话断开
- **THEN** 旧 session_id 再回发返回 404
