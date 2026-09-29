# multi-node-sync 能力增量(节点文件变更监听)

## MODIFIED Requirements

### Requirement: Node Document Upload
Node SHALL 在扫描本地知识库后,与本地同步快照(上次确认同步成功的 path → hash 集合)比对,按差异分类推送:新增或哈希变更的文档上传**含全文**,未变更的文档仅上报 `{path, hash}`(不含 content),快照中存在而本轮扫描缺失的路径列入 `deletions`;推送通过 HTTP 携带节点令牌完成,触发时机为:初始连接成功后、收到 `sync_request` 时、本地文件变更事件经防抖聚合后,以及定时对账到点时(后两者见 `Node File Change Watch`)。SHALL 仅在收到 Hub 成功响应(200)后更新本地快照;失败时快照不变,等待下次触发重试。

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

## ADDED Requirements

### Requirement: Node File Change Watch
Node SHALL 监听本地知识库目录下的 Markdown 文件变更,并将变更事件(经防抖聚合后)转换为同步触发。监听范围 SHALL 限于已配置且存在的知识库根目录;文件过滤 SHALL 与本地扫描器使用同一套判定(扩展名、相对路径隐藏项、内置排除目录、单文件大小上限),保证"监听得到的"与"扫描得到的"一致。Node SHALL 提供定时全量对账作为兜底,SHALL 对同一时刻的多个同步触发做串行化。监听与对账过程的异常 MUST NOT 中断 WebSocket 连接或心跳。

#### Scenario: 变更文件触发同步
- **WHEN** 知识库目录下新增或修改一个可扫描的 `.md` 文件
- **THEN** Node 在防抖窗口结束后触发增量同步,该文档以含全文的条目上传

#### Scenario: 删除文件触发删除
- **WHEN** 知识库目录下一个已同步的 `.md` 文件被删除
- **THEN** 该路径进入同步请求的 `deletions`,Hub 端对应文档被删除

#### Scenario: 局部同步不产生隐式删除
- **WHEN** 仅有单个文件发生变更并触发局部同步
- **THEN** 请求的 `deletions` 只包含明确捕获到删除事件的路径,快照中存在但本轮未扫描到的其他路径 MUST NOT 被删除

#### Scenario: 非 Markdown 与排除目录被忽略
- **WHEN** 变更事件指向非 `.md` 文件,或位于内置排除目录(如 `node_modules`)内
- **THEN** 该事件被忽略,不触发同步

#### Scenario: 连续事件被防抖聚合
- **WHEN** 同一文件在防抖窗口内产生多次变更事件
- **THEN** Node 只发起一次同步

#### Scenario: 写入未完成时跳过
- **WHEN** 变更文件在稳定性检查中大小或修改时间仍在变化
- **THEN** 本轮跳过该文件,不阻塞同轮其他文件,等待后续事件或定时对账处理

#### Scenario: 定时对账兜底
- **WHEN** 到达配置的对账间隔
- **THEN** Node 执行一次全量扫描与差异比对,补齐监听遗漏的变更

#### Scenario: 监听被关闭时仍能收敛
- **WHEN** 监听被配置为关闭
- **THEN** Node 仍按对账间隔同步变更,并在启动日志明确提示监听已关闭

#### Scenario: 并发触发被串行化
- **WHEN** 文件变更事件与 Hub 的 `sync_request` 在相近时刻先后到达
- **THEN** 同步调用被串行化,不产生重复的并发上传

#### Scenario: 监听异常不中断连接
- **WHEN** 监听或对账过程发生异常
- **THEN** Node 记录日志并退避重试,WebSocket 连接与心跳保持正常
