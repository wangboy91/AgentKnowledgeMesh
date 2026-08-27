## MODIFIED Requirements

### Requirement: Vector Storage Backend
向量存储 SHALL 使用 PostgreSQL + pgvector，表结构自动初始化，并在嵌入维度变化时自动重建。

#### Scenario: 懒初始化
- **WHEN** 首次使用向量功能
- **THEN** 系统确保 `vector` 扩展存在并创建向量表（默认表名 `document_vectors`，含 doc_id、标题、路径、node_id、分块序号、分块内容、embedding 列）及 doc_id 索引

#### Scenario: 维度自动检测
- **WHEN** 未显式配置 `AKM_VECTOR_DIMENSIONS`（值为 0）
- **THEN** 系统通过嵌入探测文本自动确定向量维度

#### Scenario: 嵌入模型切换后重建
- **WHEN** 现有向量表的嵌入维度与当前模型不一致
- **THEN** 系统删除并重建向量表（旧向量与新模型不兼容）

#### Scenario: 相似度索引按维度选择
- **WHEN** 初始化向量索引
- **THEN** 维度 ≤ 2000 时创建 HNSW 余弦相似度索引；更高维度使用 halfvec 表达式索引

#### Scenario: 向量库连接回退
- **WHEN** 未单独配置向量库连接参数
- **THEN** 向量库复用主数据库的连接配置（单一数据库部署）

### Requirement: Embedding Provider Configuration
系统 SHALL 支持通过 `AKM_EMBEDDING_PROVIDER` 切换嵌入供应商：`ark`（默认，火山引擎 Ark API，模型 `doubao-embedding-vision-250615`，需 `AKM_ARK_API_KEY`）或 `local`（本地 sentence-transformers）。

#### Scenario: 默认 Ark 供应商
- **WHEN** 未配置嵌入供应商
- **THEN** 系统使用火山引擎 Ark API 生成嵌入

#### Scenario: 本地嵌入切换
- **WHEN** 配置 `AKM_EMBEDDING_PROVIDER=local`
- **THEN** 系统使用本地 sentence-transformers 生成嵌入，无需外部 API
