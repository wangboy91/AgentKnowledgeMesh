## ADDED Requirements

### Requirement: Strict Owner Readonly Vector Barrier
系统 SHALL 在 owner-readonly-v1 下禁止旧 RAG/向量检索入口与向量库启动初始化；新链路 MUST NOT 创建 Hub embedding、正文 chunk 或摘要副本，已有向量数据不自动清理。

#### Scenario: 严格模式隔离旧向量结果
- **WHEN** profile 开启且客户端请求旧 RAG 检索
- **THEN** 返回拒绝且无旧片段，不调用嵌入服务或清理存量向量
