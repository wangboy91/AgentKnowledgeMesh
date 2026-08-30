## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: RAG Graceful Degradation
RAG 子系统故障 SHALL 不阻塞服务启动与核心文档功能。

#### Scenario: 启动时向量初始化失败
- **WHEN** 服务启动时向量表初始化失败（如无 PostgreSQL 连接）
- **THEN** 系统记录告警并继续启动，文档与搜索功能正常可用

#### Scenario: 文本分块
- **WHEN** 文档被向量化
- **THEN** 系统按 token 计数并保持 Markdown 结构分块（详见 Markdown-Aware Chunking），不超过上限的文本作为单块返回
