## ADDED Requirements

### Requirement: Strict Owner Readonly Indexing Barrier
系统 SHALL 在 owner-readonly-v1 下隔离旧扫描/全文上传和内容索引入口，不为新 owner 文件在 Hub 持久化正文索引、chunk 或 embedding。既有内容索引 SHALL 保留待显式迁移确认，不自动删除。

#### Scenario: 严格模式没有新增内容索引
- **WHEN** profile 开启且 Node 回报 owner 文件元数据
- **THEN** Hub 只提交 owner 元数据，原内容索引不向严格读取提供回退
