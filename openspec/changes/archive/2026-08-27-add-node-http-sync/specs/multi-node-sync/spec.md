## ADDED Requirements

### Requirement: Node Document Upload
Node SHALL 在扫描本地知识库后，将完整文档列表（含 path、title、hash、size、content）通过 HTTP 推送到 Hub 的节点文档入库端点，并携带注册时下发的节点令牌鉴权；触发时机为初始连接成功后与收到 `sync_request` 时。

#### Scenario: 初始连接后上传
- **WHEN** Node 成功注册到 Hub
- **THEN** Node 扫描本地知识库并向 Hub 推送全部文档，记录 Hub 返回的同步统计

#### Scenario: 收到同步请求后上传
- **WHEN** Node 收到 `{"type": "sync_request"}` 消息
- **THEN** Node 重新扫描本地知识库并推送文档列表到 Hub

#### Scenario: 上传鉴权失败
- **WHEN** Node 携带的令牌无效（Hub 返回 401）
- **THEN** Node 记录错误日志，不中断 WebSocket 连接，等待下一次同步触发重试

### Requirement: Hub Node Document Ingestion
Hub SHALL 提供 `PUT /api/nodes/{node_id}/documents` 端点，接收节点推送的文档列表，按 `(node_id, path)` 作用域增量入库：SHA256 哈希不同的文档更新、列表中缺失的该节点文档删除，并返回同步统计。

#### Scenario: 新增与更新文档
- **WHEN** 节点推送的文档列表中包含 Hub 该节点名下不存在或哈希已变的路径
- **THEN** Hub 插入或更新对应文档记录，统计中计入 created/updated 计数

#### Scenario: 清理消失文档
- **WHEN** 节点推送的文档列表缺少 Hub 该节点名下已存在的某路径
- **THEN** Hub 删除该节点的该文档记录，统计中计入 deleted 计数

#### Scenario: 作用域隔离
- **WHEN** 节点推送文档列表
- **THEN** Hub 仅增删改 `node_id` 等于路径中节点标识的文档，绝不修改 `local` 或其他节点的文档

#### Scenario: 未鉴权或节点不存在
- **WHEN** 请求未携带有效令牌，或 `node_id` 不存在
- **THEN** Hub 返回 401（令牌无效）或 404（节点不存在）

### Requirement: Node Token Issuance
Hub SHALL 在节点注册时下发（首次生成并持久化、后续复用）节点令牌，并在 `register_ack` 消息中返回；节点文档入库端点 SHALL 强制校验该令牌。

#### Scenario: 注册返回令牌
- **WHEN** 节点发送合法 `register` 消息
- **THEN** Hub 返回 `{"type": "register_ack", "node_id": ..., "status": "ok", "token": ...}`，令牌持久化于节点记录中

#### Scenario: 令牌稳定复用
- **WHEN** 同一 `node_id` 再次注册
- **THEN** Hub 返回与该节点首次注册时一致的令牌，而非重新生成

#### Scenario: 端点校验令牌
- **WHEN** 请求访问 `PUT /api/nodes/{node_id}/documents`
- **THEN** Hub 校验 `Authorization: Bearer <token>` 与节点记录中的令牌一致，不一致时返回 401
