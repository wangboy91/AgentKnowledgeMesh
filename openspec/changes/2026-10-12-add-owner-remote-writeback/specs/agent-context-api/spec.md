## ADDED Requirements

### Requirement: Strict Owner Readonly Context Barrier
系统 SHALL 在 owner-readonly-v1 下隔离旧 Context API 的 Hub 正文查询，不从旧全文、片段或历史正文向调用者返回内容；默认模式 SHALL 保留原接口。

#### Scenario: 严格模式 Context 停供旧正文
- **WHEN** profile 已开启且请求旧 Context API
- **THEN** 返回 409 且不含正文或片段
