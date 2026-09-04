## MODIFIED Requirements

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
