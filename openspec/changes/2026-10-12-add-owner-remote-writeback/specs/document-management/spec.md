## ADDED Requirements

### Requirement: Strict Owner Readonly Document Barrier
系统 SHALL 在显式开启 owner-readonly-v1 时隔离旧文档列表/树/详情/正文写入与扫描端点，返回不含正文的拒绝结果；默认关闭该 profile 时保留既有文档能力。新 owner 元数据/实时正文 SHALL 使用 owner-files 独立入口，旧数据库内容 MUST NOT 被隐式迁移或删除。

#### Scenario: 严格模式下访问旧文档端点
- **WHEN** profile 已开启且请求旧文档列表、树、详情或写入
- **THEN** 返回 409 且无正文；旧数据保留，新实时读取按 owner-files 权限与墓碑规则执行
