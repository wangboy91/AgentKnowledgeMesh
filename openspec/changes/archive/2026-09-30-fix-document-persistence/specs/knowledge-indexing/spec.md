# knowledge-indexing Specification (delta)

## MODIFIED Requirements

### Requirement: Incremental Index Sync
系统 SHALL 基于路径匹配与 SHA256 哈希对比执行增量索引：新增文档插入、内容变化更新、文件消失删除，并返回同步统计。**增量同步的作用域 SHALL 限于内容来源(`origin`)为 `file` 的文档:来源为 `agent`(由 Hub/智能体写入)的文档 SHALL NOT 被扫描结果覆盖,亦 SHALL NOT 因未出现在扫描结果中而被删除。当扫描结果中出现与既有 `agent` 来源文档相同的路径时,系统 SHALL 跳过该条目、计入 `skipped` 统计并记录告警,SHALL NOT 覆盖既有文档、亦 SHALL NOT 因插入同名记录而违反 `(node_id, path)` 唯一约束。**

#### Scenario: 新文档入库
- **WHEN** 扫描结果中出现索引中不存在的路径
- **THEN** 系统创建索引记录（路径唯一性按 `(node_id, path)` 约束），统计 `created` 计数加一

#### Scenario: 内容变化触发更新
- **WHEN** 已索引路径的 SHA256 哈希与扫描结果不同
- **THEN** 系统更新该记录的标题、哈希、大小与内容，统计 `updated` 计数加一

#### Scenario: 消失文件清理
- **WHEN** 已索引路径未出现在本次扫描结果中
- **THEN** 系统删除该索引记录，统计 `deleted` 计数为其数量

#### Scenario: agent 来源文档不被扫描覆盖
- **WHEN** 某文档 `origin` 为 `agent`,且扫描结果中同一路径的内容与库中不一致
- **THEN** 系统不修改该文档的标题、哈希、大小与内容,统计 `skipped` 计数加一,`updated` 不增加

#### Scenario: agent 来源文档不被扫描删除
- **WHEN** 某文档 `origin` 为 `agent`,且其路径未出现在本次扫描结果中
- **THEN** 系统保留该记录,`deleted` 不增加

#### Scenario: agent 来源文档不影响 file 来源文档的删除推导
- **WHEN** 同一归属下同时存在 `agent` 与 `file` 来源的文档,扫描结果缺少某 `file` 来源文档的路径
- **THEN** 该 `file` 来源文档被删除并计入 `deleted`,`agent` 来源文档不受影响

### Requirement: Document Data Model
文档索引记录 SHALL 包含：自增主键、节点标识（本地文档默认 `local`）、路径、标题、SHA256 哈希、字节大小、标签（JSON 数组）、全文内容、创建与更新时间，且 `(node_id, path)` 组合唯一。**记录 SHALL 另含内容来源 `origin`,取值 `file`(内容由文件扫描派生,默认值)或 `agent`(内容由 Hub/智能体写入、无对应磁盘文件);该字段 SHALL 随文档对象一并返回,供调用方判断文档是否受文件事件影响。**

#### Scenario: 本地文档默认节点标识
- **WHEN** Hub 本地扫描创建文档记录
- **THEN** 记录的 `node_id` 为 `local`

#### Scenario: 同节点路径唯一
- **WHEN** 同一节点下出现重复路径的文档
- **THEN** 唯一约束 `(node_id, path)` 阻止重复记录

#### Scenario: 来源字段默认值与取值
- **WHEN** 记录由文件扫描(Hub 本机目录或节点上传)创建,未显式指定来源
- **THEN** 记录的 `origin` 为 `file`;而经 REST / MCP 写入口径创建或更新的记录,`origin` 为 `agent`

#### Scenario: 存量记录迁移后的来源
- **WHEN** 既有数据库经列迁移补上 `origin` 列
- **THEN** 全部存量记录 `origin` 为 `file`,其可被扫描覆盖与删除的行为与迁移前一致
