## ADDED Requirements

### Requirement: Strict Owner Readonly Metadata Transport
系统 SHALL 在 owner-readonly-v1 下拒绝旧 /ws 与节点全文 documents/sync 通道；Node SHALL 不运行旧全文同步，仅通过独立 owner-ws 上报身份/版本/hash/可达性/墓碑元数据并实时内存响应只读请求。默认模式 SHALL 保留原同步能力。

#### Scenario: 严格模式不上传全文
- **WHEN** 显式启用 owner-readonly-v1
- **THEN** 旧全文通道被拒绝；manifest 不含 content，根不可达不产生删除，write action 明确不支持
