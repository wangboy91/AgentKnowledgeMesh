# multi-node-sync 能力规格

## Purpose

Hub + Node 分布式架构：节点通过 WebSocket 连接 Hub 注册与心跳，支持文档同步消息与节点管理，实现多台机器共享知识。

## Requirements

### Requirement: Node Connection and Registration
系统 SHALL 在 `/ws` 提供 WebSocket 端点；节点连接后的第一条消息 MUST 为 `register`，携带 `node_id`、`name`、`platform`。

#### Scenario: 注册成功
- **WHEN** 节点发送合法的 `register` 消息
- **THEN** Hub 持久化或更新该节点记录（状态置为 `online`，刷新 `last_heartbeat`），返回 `{"type": "register_ack", "node_id": ..., "status": "ok"}` 并保持连接

#### Scenario: 注册消息缺少 node_id
- **WHEN** `register` 消息缺少 `node_id`
- **THEN** Hub 返回 `{"type": "error", "message": "Missing node_id"}`

#### Scenario: 注册失败关闭连接
- **WHEN** 首条消息不是合法注册（未产生有效 node_id）
- **THEN** Hub 以关闭码 4001（"Registration failed"）关闭连接

#### Scenario: 未知消息类型
- **WHEN** Hub 收到未知 `type` 的消息
- **THEN** Hub 返回 `{"type": "error", "message": "Unknown message type: ..."}`

### Requirement: Node Identity
Node 客户端 SHALL 在未显式配置时自动生成本机身份：`node_id` 由主机名确定性生成（UUID5），`name` 默认为主机名，`platform` 为小写操作系统名（darwin/windows/linux）。

#### Scenario: 同机重启身份不变
- **WHEN** 同一台机器未配置 `AKM_NODE_ID` 并重启 Node
- **THEN** 生成的 `node_id` 与之前相同，Hub 识别为同一节点

#### Scenario: 显式配置优先
- **WHEN** 配置了 `AKM_NODE_ID` 或 `AKM_NODE_NAME`
- **THEN** Node 使用配置值而非自动生成值

### Requirement: Heartbeat Keep-Alive
Node SHALL 周期性向 Hub 发送 `heartbeat` 消息（默认间隔 30 秒，可通过 `AKM_HEARTBEAT_INTERVAL` 配置）；Hub SHALL 以心跳刷新节点在线状态。

#### Scenario: 心跳刷新状态
- **WHEN** Hub 收到节点的 `heartbeat` 消息
- **THEN** Hub 更新该节点 `last_heartbeat` 为当前时间、状态置为 `online`，并返回 `{"type": "heartbeat_ack"}`

### Requirement: Node Online State
Hub SHALL 通过内存中的连接管理器跟踪在线节点；连接断开时节点状态 MUST 置为 `offline`。

#### Scenario: 断线标记离线
- **WHEN** 节点 WebSocket 连接断开
- **THEN** Hub 将该节点数据库状态置为 `offline` 并从在线列表移除

#### Scenario: Node 自动重连
- **WHEN** Node 与 Hub 的连接断开
- **THEN** Node 在 5 秒后尝试重新连接并重新注册

### Requirement: Document Sync Messaging
协议 SHALL 支持文档同步相关消息：Hub 向节点发送 `sync_request` 请求扫描同步，发送 `doc_request` 请求指定路径文档；节点以 `doc_response` 返回文档内容（含 path、content、title、hash、size），并可通过 `doc_update`（action 为 create/update/delete）通知文档变更。

#### Scenario: 节点响应文档请求
- **WHEN** 节点收到 `{"type": "doc_request", "path": ...}`
- **THEN** 节点在本地扫描结果中查找该路径，命中时发送 `doc_response` 消息回传完整文档信息

#### Scenario: 节点通知文档变更
- **WHEN** 节点本地文档发生增删改
- **THEN** 节点发送 `doc_update` 消息（含 `action`），Hub 回复 `doc_update_ack`

### Requirement: Node Management API
系统 SHALL 提供节点管理 REST API：列表、详情、节点文档、触发同步、删除。

#### Scenario: 节点列表反映实时在线状态
- **WHEN** 客户端调用 `GET /api/nodes`
- **THEN** 系统返回全部节点（按注册时间倒序），当前持有活跃连接的节点状态为 `online`

#### Scenario: 节点详情
- **WHEN** 客户端调用 `GET /api/nodes/{node_id}`
- **THEN** 系统返回节点信息，状态按实时连接判断；节点不存在时返回 404

#### Scenario: 查询节点文档
- **WHEN** 客户端调用 `GET /api/nodes/{node_id}/documents`
- **THEN** 系统返回该节点信息及其名下文档列表（按更新时间倒序、不含正文）；节点不存在时返回 404

#### Scenario: 触发在线节点同步
- **WHEN** 客户端对在线节点调用 `POST /api/nodes/{node_id}/sync`
- **THEN** Hub 向该节点发送 `sync_request` 消息并返回 `{"message": "Sync request sent"}`

#### Scenario: 对离线节点触发同步
- **WHEN** 客户端对离线节点调用 `POST /api/nodes/{node_id}/sync`
- **THEN** 系统返回 400，`detail` 为 "Node is offline"

#### Scenario: 删除节点级联清理
- **WHEN** 客户端调用 `DELETE /api/nodes/{node_id}`
- **THEN** 系统删除该节点的全部文档索引及其向量分块，再删除节点记录；节点不存在时返回 404

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
Hub SHALL 提供 `PUT /api/nodes/{node_id}/documents` 端点，接收节点推送的文档列表，按 `(node_id, path)` 作用域增量入库：SHA256 哈希不同的文档更新、列表中缺失的该节点文档删除，并返回同步统计。入库的同时 SHALL 维护向量索引：created/updated 的文档在后台生成向量，deleted 的文档清理其向量；向量操作失败 SHALL 仅记录告警、不影响同步响应。

#### Scenario: 新增与更新文档
- **WHEN** 节点推送的文档列表中包含 Hub 该节点名下不存在或哈希已变的路径
- **THEN** Hub 插入或更新对应文档记录，统计中计入 created/updated 计数

#### Scenario: 新增与更新文档后台生成向量
- **WHEN** 本次同步产生 created 或 updated 文档
- **THEN** Hub 在返回同步统计后，于后台对这些文档分块、嵌入并写入向量表（覆盖其旧向量），同步响应不因嵌入耗时阻塞

#### Scenario: 哈希未变不重复嵌入
- **WHEN** 节点推送的文档哈希与 Hub 已存记录一致
- **THEN** Hub 不对该文档重新分块或嵌入

#### Scenario: 清理消失文档
- **WHEN** 节点推送的文档列表缺少 Hub 该节点名下已存在的某路径
- **THEN** Hub 删除该节点的该文档记录，统计中计入 deleted 计数

#### Scenario: 删除文档同步清理向量
- **WHEN** 本次同步删除了该节点名下的文档
- **THEN** Hub 删除这些文档在向量表中的全部分块

#### Scenario: 嵌入失败降级
- **WHEN** 后台嵌入或向量清理发生异常
- **THEN** Hub 记录告警日志，同步响应仍正常返回统计，已入库文档不受影响

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
