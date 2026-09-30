# multi-node-sync · delta

## MODIFIED Requirements

### Requirement: Node Document Upload
Node SHALL 在扫描本地知识库后,与本地同步快照(上次确认同步成功的 path → hash 集合)比对,按差异分类推送:新增或哈希变更的文档上传**含全文**,未变更的文档仅上报 `{path, hash}`(不含 content),快照中存在而本轮扫描缺失的路径列入 `deletions`;推送通过 HTTP 携带节点令牌完成,触发时机为:初始连接成功后、收到 `sync_request` 时、本地文件变更事件经防抖聚合后,以及定时对账到点时(后两者见 `Node File Change Watch`)。SHALL 仅在收到 Hub 成功响应(200)后更新本地快照;失败时快照不变,等待下次触发重试。

当单轮推送的总体积或条目数超过配置上限时,Node MUST 将 payload **切分为多个请求串行发送**,而非单次全量提交:单请求的文档条目数 MUST 不超过 `AKM_UPLOAD_BATCH_DOCS`(默认 50),单请求的 JSON 体积 SHOULD 不超过 `AKM_UPLOAD_BATCH_BYTES`(默认 512 KiB);两者任一触顶即封批。单篇文档自身超过体积上限时 MUST 独占一批发送(不得因其过大而放弃推送)。`deletions` MUST 仅随**最后一批**发送,且每一批的 payload MUST 都携带 `deletions` 键(可为空列表),以关闭 Hub 侧"列表缺失即删除"的隐式推导。分批 MUST NOT 削弱原子性:任一批次失败(网络错误或非 200 响应)时,本轮 MUST 视为整体失败,本地快照 MUST NOT 被更新,已成功批次的入库结果保留(重传幂等)。Hub 响应中的 `rejected` 与 `created` / `updated` / `deleted` 统计 MUST 跨批汇总后再用于快照决策与日志输出。当未触发任何上限时(单批即可容纳),请求数量与 payload 结构 MUST 与未分批时一致。

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

#### Scenario: 文件变更触发上传
- **WHEN** 本地知识库中的文档发生增删改并经过防抖聚合
- **THEN** Node 按差异分类推送,无需等待重启或 Hub 请求

#### Scenario: 定时对账触发上传
- **WHEN** 到达配置的对账间隔
- **THEN** Node 执行全量扫描与差异比对并推送,补齐监听遗漏的变更

#### Scenario: 快照仅在成功后更新
- **WHEN** 上传请求失败(网络错误或非 200 响应)
- **THEN** 本地快照保持不变,下轮触发时按相同差异重试

#### Scenario: 上传鉴权失败
- **WHEN** Node 携带的令牌无效(Hub 返回 401)
- **THEN** Node 记录错误日志,不中断 WebSocket 连接,等待下一次同步触发重试

#### Scenario: 超量文档切分为多批
- **WHEN** 单轮待推送的文档条目数超过 `AKM_UPLOAD_BATCH_DOCS`,或累计 JSON 体积超过 `AKM_UPLOAD_BATCH_BYTES`
- **THEN** Node 将其切分为多个 `PUT /api/nodes/{id}/documents` 请求串行发送,每个请求的条目数与体积均不超过对应上限,且各批文档条目合计等于本轮全部待推送文档(不重不漏)

#### Scenario: deletions 仅随最后一批
- **WHEN** 本轮推送因超限被切分为多批,且本轮存在待删除路径
- **THEN** 前序各批的 payload 携带空的 `deletions` 列表,待删除路径仅出现在最后一批的 `deletions` 中,Hub 最终删除结果与单批推送一致

#### Scenario: 单篇超限独占一批
- **WHEN** 某篇文档的单个条目体积即超过 `AKM_UPLOAD_BATCH_BYTES`
- **THEN** 该文档单独作为一个请求发送,不被跳过、不阻塞本轮其余文档的推送

#### Scenario: 分批过程中的批次失败不更新快照
- **WHEN** 多批推送过程中某一批返回非 200 响应或发生网络错误
- **THEN** Node 停止后续批次,记录失败信息,且本轮**不更新**本地快照;下轮触发时按相同差异重新推送,Hub 侧已入库的批次因幂等而不产生重复数据
