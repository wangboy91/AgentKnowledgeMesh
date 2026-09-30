# multi-node-sync Specification (delta)

## MODIFIED Requirements

### Requirement: Hub Node Document Ingestion
Hub SHALL 提供 `PUT /api/nodes/{node_id}/documents` 端点,接收节点推送的差异列表,按 `(node_id, path)` 作用域增量入库:携带 `content` 的条目按 SHA256 哈希比对插入或更新;未携带 `content` 且库中哈希一致的条目忽略;未携带 `content` 且库中哈希不一致或路径不存在的条目计入响应的 `rejected`(含 path 与原因),不计入失败响应;请求的 `deletions` 列表 SHALL 删除对应文档;响应 SHALL 返回 `{created, updated, deleted, rejected, skipped}` 统计。**内容来源(`origin`)为 `agent` 的文档 SHALL 对节点同步免疫:推送列表中命中该路径的条目 SHALL 被跳过——既不覆盖其内容、亦 SHALL NOT 计入 `rejected`(计入 rejected 会使节点将该路径移出本地快照、每轮携带全文重传而永不收敛),该情况 SHALL 计入响应的 `skipped`(含 path 与原因);`deletions` 列表与旧版协议的隐式缺失推导 SHALL NOT 删除 `agent` 来源的文档。** 入库的同时 SHALL 维护向量索引:created/updated 的文档在后台生成向量,deleted 与 rejected 外的文档删除时清理其向量;向量操作失败 SHALL 仅记录告警、不影响同步响应。

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

#### Scenario: agent 来源文档不被节点同步覆盖
- **WHEN** 该节点名下某文档 `origin` 为 `agent`(内容已由 Hub/智能体改写),节点推送该路径的条目——无论携带全文、或未携带全文且哈希不一致
- **THEN** Hub 保留该文档现有内容不变,该条目计入 `skipped`(原因标明来源为 agent)且 SHALL NOT 计入 `rejected`;响应中该路径不出现在 `rejected` 内,故节点不会在下一轮携带全文重传

#### Scenario: agent 来源文档不被删除推导删除
- **WHEN** 该节点名下某文档 `origin` 为 `agent`,请求的 `deletions` 列表包含该路径,或旧版全量推送的列表缺少该路径
- **THEN** Hub 保留该文档,`deleted` 不增加,且不清理其向量分块

#### Scenario: file 来源文档仍由节点同步维护
- **WHEN** 该节点名下某文档 `origin` 为 `file`,节点推送该路径且携带与库中不同的全文
- **THEN** Hub 按既有语义更新其内容并计入 `updated`,`origin` 保持 `file`
