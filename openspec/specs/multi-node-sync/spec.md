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
- **WHEN** 同一台机器未配置 `AV_NODE_ID` 并重启 Node
- **THEN** 生成的 `node_id` 与之前相同，Hub 识别为同一节点

#### Scenario: 显式配置优先
- **WHEN** 配置了 `AV_NODE_ID` 或 `AV_NODE_NAME`
- **THEN** Node 使用配置值而非自动生成值

### Requirement: Heartbeat Keep-Alive
Node SHALL 周期性向 Hub 发送 `heartbeat` 消息（默认间隔 30 秒，可通过 `AV_HEARTBEAT_INTERVAL` 配置）；Hub SHALL 以心跳刷新节点在线状态。

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
- **THEN** 系统删除该节点的全部文档索引，再删除节点记录；节点不存在时返回 404
