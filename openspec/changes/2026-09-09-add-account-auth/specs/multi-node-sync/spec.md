# multi-node-sync 能力增量(账号鉴权联动)

## MODIFIED Requirements

### Requirement: Node Connection and Registration
系统 SHALL 在 `/ws` 提供 WebSocket 端点;节点连接后的第一条消息 MUST 为 `register`,携带 `node_id`、`name`、`platform` 与 `token`;Hub SHALL 校验 `node_id + token` 与节点记录一致且节点未被禁用,校验通过方可注册。**匿名注册(未携带 token)一律拒绝。**

#### Scenario: 注册成功
- **WHEN** 节点发送携带有效 `token` 的合法 `register` 消息
- **THEN** Hub 持久化或更新该节点记录(状态置为 `online`,刷新 `last_heartbeat`),返回 `{"type": "register_ack", "node_id": ..., "status": "ok", "token": ...}` 并保持连接

#### Scenario: 匿名注册被拒
- **WHEN** `register` 消息未携带 `token`
- **THEN** Hub 以关闭码 4001 关闭连接,不建立节点会话

#### Scenario: 令牌不匹配或节点被禁用
- **WHEN** `register` 消息携带的 `token` 与节点记录不一致,或该节点已被禁用
- **THEN** Hub 以关闭码 4001 关闭连接

#### Scenario: 注册消息缺少 node_id
- **WHEN** `register` 消息缺少 `node_id`
- **THEN** Hub 返回 `{"type": "error", "message": "Missing node_id"}`

#### Scenario: 注册失败关闭连接
- **WHEN** 首条消息不是合法注册(未产生有效 node_id)
- **THEN** Hub 以关闭码 4001("Registration failed")关闭连接

#### Scenario: 未知消息类型
- **WHEN** Hub 收到未知 `type` 的消息
- **THEN** Hub 返回 `{"type": "error", "message": "Unknown message type: ..."}`

### Requirement: Node Token Issuance
节点令牌 SHALL 由 CLI 登录流颁发:节点机以管理员凭证调用 `POST /api/nodes/register`(见 account-auth 能力),Hub 创建或更新节点记录并**轮换生成**新令牌返回;此后 WS `register_ack` 返回该已存令牌用于确认。节点文档入库端点 SHALL 强制校验令牌;令牌的重置与禁用由 account-auth 能力定义。

#### Scenario: 登录接入获得令牌
- **WHEN** 节点机执行 `akm-node login` 并以管理员凭证调用注册端点
- **THEN** Hub 返回 `node_id` 与新轮换的节点令牌,节点将其写入本地配置

#### Scenario: 注册返回令牌
- **WHEN** 节点以有效令牌发送 `register` 消息
- **THEN** Hub 返回 `{"type": "register_ack", "node_id": ..., "status": "ok", "token": ...}`,令牌持久化于节点记录中

#### Scenario: 令牌稳定复用
- **WHEN** 同一 `node_id` 再次以有效令牌注册
- **THEN** Hub 返回该节点已持久化的同一令牌,而非重新生成

#### Scenario: 端点校验令牌
- **WHEN** 请求访问 `PUT /api/nodes/{node_id}/documents`
- **THEN** Hub 校验 `Authorization: Bearer <token>` 与节点记录中的令牌一致,不一致时返回 401
