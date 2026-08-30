# vector-search 能力规格

## Purpose

将文档向量化存储于 PostgreSQL + pgvector，提供语义搜索与 RAG 上下文组装，补充关键词搜索的语义级检索能力。

## Requirements

### Requirement: Markdown-Aware Chunking
系统 SHALL 在向量化前按 token 计数将文档分块，并保持 Markdown 结构完整性：按标题层级切分，表格与代码块不跨块切碎，每个 chunk 前置其所属标题作为上下文。

#### Scenario: 标题层级分块
- **WHEN** 文档包含多级 Markdown 标题
- **THEN** 系统按标题层级切分，各级标题下内容作为独立 chunk，而非仅按固定长度硬切

#### Scenario: 表格与代码块不切碎
- **WHEN** 文档包含 Markdown 表格或代码块
- **THEN** 系统分块时不将表格或代码块从中间切断，整块保留在同一个 chunk 中

#### Scenario: 标题前置上下文
- **WHEN** 系统生成文档 chunk
- **THEN** 每个 chunk 的内容前置其所属标题路径（如 `## 章节名`），使向量携带结构上下文

#### Scenario: token 计数分块
- **WHEN** 文档 token 数超过分块上限
- **THEN** 系统以 token（而非字符）度量块大小，接近上限时在断句点切分，块间保留重叠

#### Scenario: 短文档单块
- **WHEN** 文档 token 数不超过分块上限
- **THEN** 整篇文档作为单个 chunk 返回

### Requirement: Semantic Search Endpoint
系统 SHALL 提供 `GET /api/rag/search` 端点，基于向量相似度与关键词匹配进行混合检索，以 RRF 融合两侧结果，并返回满足相似度阈值的相关分块（同一文档可返回多个分块）。

#### Scenario: 语义检索
- **WHEN** 客户端调用 `GET /api/rag/search?q=<查询文本>`
- **THEN** 系统分别执行向量检索与关键词匹配，融合后按相关度排序返回 `{"query", "count", "results": [{"doc_id", "title", "path", "node_id", "chunk", "score"}]}`，limit 范围 1–20（默认 5），支持 `node_id` 过滤

#### Scenario: 同文档只保留最佳分块
- **WHEN** 同一文档的多个分块均与查询相关
- **THEN** 系统返回该文档的多个最佳分块（每文档有数量上限），而非仅保留一个分块

#### Scenario: 相似度阈值过滤
- **WHEN** 检索候选中存在相似度低于阈值的项
- **THEN** 系统不返回这些低于阈值的候选，而非无条件凑满 limit

#### Scenario: 关键词精确命中
- **WHEN** 查询包含文件名、ID 或专有名词等精确词项
- **THEN** 关键词匹配确保这些精确命中进入融合候选，弥补纯向量检索的漏检

#### Scenario: 检索失败降级
- **WHEN** 向量检索过程发生异常（如数据库不可用）
- **THEN** 系统返回 `{"query", "count": 0, "results": [], "error": <信息>}`，不抛出 500

### Requirement: RAG Context Assembly
系统 SHALL 提供 `GET /api/rag/context` 端点，返回语义相关文档的完整内容，用于 RAG prompt 组装。

#### Scenario: 组装上下文
- **WHEN** 客户端调用 `GET /api/rag/context?q=<查询文本>`
- **THEN** 系统先语义检索（limit 范围 1–10、默认 3，支持 `node_id` 过滤），再按检索顺序取回全文，返回每篇文档的 title、content、path、node_id、score 与 matched_chunk

#### Scenario: 无检索结果
- **WHEN** 语义检索无命中
- **THEN** 返回 `{"query", "count": 0, "documents": []}`

#### Scenario: 组装失败降级
- **WHEN** 组装过程发生异常
- **THEN** 系统返回 count 0 与 error 信息，不抛出 500

### Requirement: Vector Index Management
系统 SHALL 提供 `POST /api/rag/index` 端点，将数据库中全部含内容的文档向量化入库；文档增删改时 SHALL 尽力同步向量索引。

#### Scenario: 全量索引
- **WHEN** 客户端调用 `POST /api/rag/index`
- **THEN** 系统遍历全部文档，对每篇有内容的文档分块、嵌入并写入向量表，返回 `{"message", "indexed": N, "total_chunks": M}`

#### Scenario: 重复索引覆盖旧向量
- **WHEN** 对已索引文档再次入库
- **THEN** 系统先删除该文档的旧分块向量再写入新向量

#### Scenario: 文档生命周期同步
- **WHEN** 文档经索引同步或文档 API 创建/更新/删除
- **THEN** 系统尽力同步向量索引（新增/覆盖/删除对应向量）；向量操作失败仅记录告警，不影响主流程

#### Scenario: 索引失败降级
- **WHEN** 全量索引过程发生异常
- **THEN** 系统返回 `{"message": "Index failed: ...", "indexed": 0}`，不抛出 500

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

### Requirement: Vector Stats Endpoint
系统 SHALL 提供 `GET /api/rag/stats` 端点，返回向量存储统计。

#### Scenario: 返回分块总数
- **WHEN** 客户端调用 `GET /api/rag/stats`
- **THEN** 系统返回 `{"total_chunks": N}`；异常时返回 `{"total_chunks": 0, "error": ...}`

### Requirement: Embedding Provider Configuration
系统 SHALL 支持通过 `AKM_EMBEDDING_PROVIDER` 切换嵌入供应商：`ark`（默认，火山引擎 Ark API，模型 `doubao-embedding-vision-250615`，需 `AKM_ARK_API_KEY`）或 `local`（本地 sentence-transformers）。

#### Scenario: 默认 Ark 供应商
- **WHEN** 未配置嵌入供应商
- **THEN** 系统使用火山引擎 Ark API 生成嵌入

#### Scenario: 本地嵌入切换
- **WHEN** 配置 `AKM_EMBEDDING_PROVIDER=local`
- **THEN** 系统使用本地 sentence-transformers 生成嵌入，无需外部 API

### Requirement: RAG Graceful Degradation
RAG 子系统故障 SHALL 不阻塞服务启动与核心文档功能。

#### Scenario: 启动时向量初始化失败
- **WHEN** 服务启动时向量表初始化失败（如无 PostgreSQL 连接）
- **THEN** 系统记录告警并继续启动，文档与搜索功能正常可用

#### Scenario: 文本分块
- **WHEN** 文档被向量化
- **THEN** 系统按 token 计数并保持 Markdown 结构分块（详见 Markdown-Aware Chunking），不超过上限的文本作为单块返回
