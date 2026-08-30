## Why

当前 RAG 检索是纯稠密向量的朴素基线：切片按 500 字符硬切、无视 Markdown 结构；召回无关键词融合、无相似度阈值、每文档只保留一个最佳分块。对 Markdown 知识库，切片会把表格/代码块/标题结构切碎，exact 匹配（文件名、ID、专有名词）被 dense 检索漏掉，召回率与精度都达不到企业级可用。需要升级为行业最佳实践：结构化切片 + 混合检索 + 可度量评测。

## What Changes

- **分块**：由字符计数改为 token 计数 + Markdown 感知（标题层级、表格与代码块不切碎、标题前置到每个 chunk）。
- **检索**：由纯 dense 改为 dense ⊕ sparse 混合检索（sparse 侧使用 PostgreSQL `pg_trgm` 关键词匹配），以 RRF（Reciprocal Rank Fusion）融合两侧结果。
- **召回**：解除「每文档单 chunk」限制，支持每文档返回多个匹配 chunk 并按文档去重聚合。
- **精度**：新增相似度阈值，低于阈值的候选不再返回。
- **评测**：新增检索质量评测 harness，以标注 query 集计算 `recall@k` 与 `nDCG@10`，支持改前/改后对比。

**明确非目标（Non-goals，后续单独 change）**：rerank（本地 cross-encoder）、嵌入模型更换（保留 `doubao-embedding-vision`）。

## Capabilities

### New Capabilities

（无。评测 harness 属内部工具，不对应运行时能力规格。）

### Modified Capabilities

- `vector-search`：分块规则（Markdown 感知 + token 计数）、检索策略（混合检索 + RRF + 相似度阈值 + 每文档多 chunk）发生 spec 级行为变化。

## Impact

- **代码**：`src/server/app/services/rag/embeddings.py`（重写 `chunk_text`）、`src/server/app/services/rag/vector_store.py`（改造 `search`/`add_document`、新增 trigram 索引）、`src/server/app/api/rag.py`（检索参数与返回结构）。
- **依赖**：PostgreSQL 内置 `pg_trgm` 扩展（contrib，需在向量库确认可用，无需额外安装）。
- **数据库**：新增 trigram 索引；向量表结构不变，无迁移破坏。
- **评测**：新增标注数据集文件与评测脚本（小规模手工标注起步，可扩展）。
