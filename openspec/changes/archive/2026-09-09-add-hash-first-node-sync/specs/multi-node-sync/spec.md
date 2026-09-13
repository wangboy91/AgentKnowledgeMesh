# multi-node-sync 能力增量(hash-first 同步)

## MODIFIED Requirements

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
