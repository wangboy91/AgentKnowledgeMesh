# multi-node-sync 能力规格

## Purpose

Hub + Node 分布式架构：节点通过 WebSocket 连接 Hub 注册与心跳，支持文档同步消息与节点管理，实现多台机器共享知识。

## Requirements

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
Node SHALL 在扫描本地知识库后,与本地同步快照(上次确认同步成功的 path → hash 集合)比对,按差异分类推送:新增或哈希变更的文档上传**含全文**,未变更的文档仅上报 `{path, hash}`(不含 content),快照中存在而本轮扫描缺失的路径列入 `deletions`;推送通过 HTTP 携带节点令牌完成,触发时机为初始连接成功后与收到 `sync_request` 时。SHALL 仅在收到 Hub 成功响应(200)后更新本地快照;失败时快照不变,等待下次触发重试。

#### Scenario: 初始连接后上传
- **WHEN** Node 成功注册到 Hub 且本地无快照(首次)
- **THEN** Node 上传全部文档(含全文),成功后将扫描结果写入快照

#### Scenario: 无变更轮次近乎零流量
- **WHEN** 本轮扫描结果与快照完全一致
- **THEN** 上传请求仅携带各文档的 path 与 hash(无 content),不携带 deletions

#### Scenario: 变更文档携带全文
- **WHEN** 某文档为新增或哈希相对快照已变化
- **THEN** 该文档条目包含完整 content

#### Scenario: 收到同步请求后上传
- **WHEN** Node 收到 `{"type": "sync_request"}` 消息
- **THEN** Node 重新扫描、按差异分类并推送到 Hub

#### Scenario: 快照仅在成功后更新
- **WHEN** 上传请求失败(网络错误或非 200 响应)
- **THEN** 本地快照保持不变,下轮触发时按相同差异重试

#### Scenario: 上传鉴权失败
- **WHEN** Node 携带的令牌无效(Hub 返回 401)
- **THEN** Node 记录错误日志,不中断 WebSocket 连接,等待下一次同步触发重试

### Requirement: Hub Node Document Ingestion
Hub SHALL 提供 `PUT /api/nodes/{node_id}/documents` 端点,接收节点推送的差异列表,按 `(node_id, path)` 作用域增量入库:携带 `content` 的条目按 SHA256 哈希比对插入或更新;未携带 `content` 且库中哈希一致的条目忽略;未携带 `content` 且库中哈希不一致或路径不存在的条目计入响应的 `rejected`(含 path 与原因),不计入失败响应;请求的 `deletions` 列表 SHALL 删除对应文档;响应 SHALL 返回 `{created, updated, deleted, rejected}` 统计。入库的同时 SHALL 维护向量索引:created/updated 的文档在后台生成向量,deleted 与 rejected 外的文档删除时清理其向量;向量操作失败 SHALL 仅记录告警、不影响同步响应。

#### Scenario: 新增与更新文档
- **WHEN** 推送列表中包含该节点名下不存在或哈希已变且携带 content 的路径
- **THEN** Hub 插入或更新对应文档记录,统计计入 created/updated

#### Scenario: 未变更条目忽略
- **WHEN** 条目未携带 content 且库中该路径哈希与上报 hash 一致
- **THEN** 不产生任何写操作,不计入统计

#### Scenario: 哈希不一致且无全文
- **WHEN** 条目未携带 content 且库中该路径哈希与上报 hash 不一致(或路径不存在)
- **THEN** 该条目计入 rejected(含原因),不入库;节点下轮将携带全文重传

#### Scenario: 删除列表生效
- **WHEN** 请求携带 `deletions: ["c.md"]` 且该节点名下存在该路径
- **THEN** 删除该文档并清理其向量分块,统计计入 deleted

#### Scenario: 新增与更新文档后台生成向量
- **WHEN** 本次同步产生 created 或 updated 文档
- **THEN** Hub 在返回统计后于后台分块、嵌入并写入向量表(覆盖其旧向量),同步响应不因嵌入耗时阻塞

#### Scenario: 哈希未变不重复嵌入
- **WHEN** 携带 content 的条目哈希与 Hub 已存记录一致
- **THEN** Hub 不对该文档重新分块或嵌入

#### Scenario: 清理消失文档
- **WHEN** 请求条目均携带 content(旧版全量推送)且列表缺少该节点名下已存在的某路径
- **THEN** Hub 删除该节点的该文档记录,统计中计入 deleted 计数

#### Scenario: 删除文档同步清理向量
- **WHEN** 本次同步删除了该节点名下的文档(deletions 列表或旧协议缺失清理)
- **THEN** Hub 删除这些文档在向量表中的全部分块

#### Scenario: 嵌入失败降级
- **WHEN** 后台嵌入或向量清理发生异常
- **THEN** Hub 记录告警日志,同步响应仍正常返回统计,已入库文档不受影响

#### Scenario: 作用域隔离
- **WHEN** 节点推送差异列表
- **THEN** Hub 仅增删改 `node_id` 等于路径中节点标识的文档,绝不修改 `local` 或其他节点的文档

#### Scenario: 未鉴权或节点不存在
- **WHEN** 请求未携带有效令牌,或 `node_id` 不存在
- **THEN** Hub 返回 401(令牌无效)或 404(节点不存在)

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
