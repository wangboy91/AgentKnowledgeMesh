## ADDED Requirements

### Requirement: Strict Owner Readonly Search Boundary
系统 SHALL 在 owner-readonly-v1 下隔离旧 Hub 全文关键词入口，Hub 仅执行 owner-files 路径元数据检索；正文查询 SHALL 转给在线且授权的 owner，结果仅在内存返回，不建 Hub 正文索引。

#### Scenario: owner 离线不伪造命中
- **WHEN** profile 开启且在线 owner 正文检索不可用
- **THEN** 返回明确不可用，不从旧 Hub 全文或缓存回退
