## Purpose

为分布在不同电脑、每个文件只有一个磁盘 owner 的知识文件提供显式授权的跨机正文写回和版本记录契约。该能力确保保存成功对应真实 owner 落盘，并在源删除被 Hub 确认后阻断新的内容读取与过期消息复活。

## ADDED Requirements

### Requirement: 稳定身份与唯一归属
系统 SHALL 以不可变 file_id、唯一 owner、generation、单调 revision 和实际字节 hash 标识纳入远程写回的文件；同路径重建 SHALL 使用新身份/代次和新授权。其他 Node MUST NOT 自动保存原文件工作副本。

#### Scenario: A 与 B 分别拥有文件
- **WHEN** A 获准修改 B 的文件、B 获准修改 A 的另一文件
- **THEN** 各修改仅写入对应唯一 owner 磁盘，文件身份与 owner 保持不变，两个相同路径不会串写

#### Scenario: 删除后同路径重建
- **WHEN** owner 删除后在同一路径重新创建文件
- **THEN** 新文件使用新 ID/代次，旧授权与旧更新不适用

### Requirement: 显式权限与路径边界
系统 SHALL 同时校验当前身份写资格、未撤销的单文件/代次 update_content 授权及 owner 可写根；Node SHALL 拒绝任意路径注入、越界和 symlink/junction/reparse point 替换竞态。无法保证边界 MUST 拒绝操作。

#### Scenario: 无授权与权限降级
- **WHEN** 匿名、viewer、只读 token、未获目标授权的节点或已撤销主体请求写回
- **THEN** 系统拒绝请求，owner 磁盘和 Hub 当前版本均不变

#### Scenario: 越界路径
- **WHEN** 请求或目标文件变化涉及 ..、UNC/盘符、ADS 或链接越界
- **THEN** Node 拒绝写盘，不修改根内外任何文件

### Requirement: 条件写入与真实保存确认
系统 SHALL 校验 base_revision、base_hash 和代次，并在 owner 原子落盘确认且 Hub 版本提交后才返回保存成功；并发本地/远程修改 MUST 返回冲突，禁止静默覆盖。版本元信息 SHALL 记录本地/远程修改的 revision、hash、时间、来源、主体和 operation_id。

#### Scenario: 成功写回
- **WHEN** 当前版本匹配、权限有效且 owner 确认实际原子写盘
- **THEN** Hub 提交新版本后返回 committed，owner 文件 hash 与 Hub 一致，版本记录可查

#### Scenario: 双方从同一版本修改
- **WHEN** 两个请求或本地编辑与远程请求竞争同一基础版本
- **THEN** 至多一个条件写回提交，另一个收到冲突并保留当前正文

#### Scenario: owner 不支持或离线
- **WHEN** owner 离线或不支持该协议
- **THEN** 拒绝新写且不排队，不报告保存成功

### Requirement: 幂等操作与未知结果
系统 SHALL 持久记录 operation_id 和请求摘要并提供授权状态查询；重复相同 ID/摘要 MUST 只执行一次，不同摘要 MUST 拒绝。落盘或 Hub 提交结果未确认时 SHALL 返回 unknown 并通过同 ID 对账，不以超时推断失败。

#### Scenario: 确认丢失与重启
- **WHEN** owner 写盘后 ack 丢失，或 Hub 提交后响应丢失并重启
- **THEN** 查询/重试原 operation_id 返回恢复后的同一结果，不新增一次写入或 revision

#### Scenario: ID 被复用
- **WHEN** 同 operation_id 提交不同内容
- **THEN** 拒绝请求，原操作状态保持不变

### Requirement: 源删除屏障与防复活
系统 SHALL 只接受 owner 对可访问根中明确文件删除的确认；Hub 提交 tombstone 后所有新请求的列表/树、详情、关键词/向量搜索、片段、Context API、API、MCP、历史正文及操作查询 MUST NOT 返回该文件内容。旧同步、索引任务及 ack MUST NOT 复活旧代次。系统 SHALL 不把不可达目录当删除，且不承诺抹去已下载外部副本或默认永久删除全部历史。

#### Scenario: A 主动删除源文件
- **WHEN** A 删除其文件并且 Hub 确认 tombstone
- **THEN** B 的全部新读取入口都不能取得正文或片段，历史正文及缓存也不能旁路

#### Scenario: 删除与延迟更新竞争
- **WHEN** tombstone 后到达旧代次上传、写回确认或索引重建
- **THEN** 保留删除状态，不重新展示任何内容

#### Scenario: 根目录不可达
- **WHEN** 目录断挂载、扫描不完整或读取权限丢失
- **THEN** 标记不可达而非 tombstone，不据此批量删除

#### Scenario: owner 离线删除
- **WHEN** owner 离线期间删除文件
- **THEN** 系统说明删除尚未同步，恢复并确认 tombstone 后才承诺所有新读取阻断

### Requirement: 正文仅归属 Node 持久保存
Hub SHALL 仅持久保存身份、owner、授权、版本、hash、删除和操作状态等元数据，MUST NOT 持久保存全文、可读 chunk、历史正文、摘要或 embedding。按需正文中转 SHALL 仅在内存，不落队列、日志、审计、错误报告、缓存或临时文件。正文读取/检索 SHALL 由在线 owner 提供，owner 离线或超时 SHALL 如实表示不可用。

#### Scenario: 查看编辑和检索
- **WHEN** 经授权客户端查看、编辑或检索正文
- **THEN** Hub 仅内存协调，客户端不自动持久保存正文；离线 owner 不产生虚假的正文命中

### Requirement: 客户端能力与信任边界
AKM 可控客户端 SHALL 禁止持久正文草稿、离线缓存与会话日志。第三方正文工具接入 SHALL 明确并验证不持久化输入/输出/会话正文的能力与信任条件；未验证 MUST 默认不开放正文工具或宣称合规。系统 MUST NOT 承诺控制第三方 Agent、浏览器扩展、OS 缓存或用户手动复制。

#### Scenario: 第三方会话持久保存
- **WHEN** 第三方客户端保存工具正文到磁盘或其行为未验证
- **THEN** 不视为满足严格另一电脑不落盘，正文工具默认不开放

### Requirement: 受控实施与旧副本迁移
系统 SHALL 对新链路显式开启且隔离旧全文路径；旧副本盘点、owner 核验、备份/历史/索引处理和存储验证完成前 MUST NOT 声称整个现有部署零正文副本。永久删除现存数据 MUST 另获用户确认。本轮已获最小代码闭环授权，未获永久清理授权。

#### Scenario: 已批准小切片而旧 Hub 仍有全文
- **WHEN** 新链路实施并在隔离数据验证，旧库尚未清理
- **THEN** 只报告新链路验证，不删除旧数据、不宣称全部署零副本


### Requirement: 默认关闭的独立只读 profile
系统 SHALL 提供显式启用的 owner-readonly-v1 profile，缺省关闭；它 SHALL 用稳定 owner 元数据、read grant、核验客户端主体及在线 owner 提供内存正文/单文件检索，根不可达/离线/超时明确失败，删除确认后停止所有新读取且墓碑不复活。该 profile MUST 隔离旧全文 REST/WS/MCP 且不清理旧数据，MUST 明确拒绝写回而不宣称完整 owner-remote-writeback 已完成。

#### Scenario: 只读切片可独立交付
- **WHEN** owner-readonly-v1 在隔离数据启用，写回契约尚未验证
- **THEN** 授权在线读取可用，旧全文通道停用，源删除后新读取停供，写回返回不支持且旧数据保留
