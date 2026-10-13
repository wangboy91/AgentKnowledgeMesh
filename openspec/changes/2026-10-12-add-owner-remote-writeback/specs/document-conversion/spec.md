## ADDED Requirements

### Requirement: Strict Owner Readonly Conversion Barrier
系统 SHALL 在 owner-readonly-v1 下隔离旧正文转换入口，避免生成 Hub 正文/临时正文副本；默认模式 SHALL 保留既有转换能力。

#### Scenario: 严格模式拒绝旧转换
- **WHEN** profile 开启且调用旧 conversion API
- **THEN** 返回拒绝且不生成 Hub 正文或临时文件
