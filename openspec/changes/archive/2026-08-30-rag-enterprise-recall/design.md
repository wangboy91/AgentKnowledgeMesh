## Context

现状（见 proposal.md - Why 了解动机）：
- 分块：`app/services/rag/embeddings.py` 的 `chunk_text`，纯字符滑窗（500 字符 + 50 重叠 + 断句点回退），无视 Markdown 结构。
- 检索：`app/services/rag/vector_store.py` 的 `search`，纯 pgvector 余弦相似度，`DISTINCT ON (doc_id)` 每文档只留一个 chunk，无阈值，无关键词侧。
- 存储：PostgreSQL + pgvector（`document_vectors` 表，HNSW 索引）；目标库已确认装有 pgvector，`pg_trgm` 为同库 contrib 扩展（待第 0 步验证）。
- 嵌入：`doubao-embedding-vision`（保留不换），逐条串行调用。

## Goals / Non-Goals

**Goals:**
- Markdown 感知 + token 计数的分块，标题前置上下文，表格/代码块不切碎。
- dense ⊕ sparse 混合检索，RRF 融合，解除「每文档单 chunk」，加相似度阈值。
- 一个能算 `recall@k` / `nDCG@10` 的评测 harness，支持改前/改后对比。

**Non-Goals:**
- rerank（本地 cross-encoder）——Phase 2 单独 change。
- 更换嵌入模型、查询改写/扩展（仅做基础分词，不做同义扩展/多路 query）。
- 向量库异步化（当前 `add_document`/`search` 走同步 psycopg2，本次不改架构，仅在其上扩展检索逻辑）。

## Decisions

### 1. 分块器位置与算法：手写 Markdown 分块器（不引入框架）

在 `app/services/rag/` 新增 `chunking.py`，实现 `chunk_markdown(text, chunk_size, chunk_overlap)`，取代 `embeddings.py` 里的 `chunk_text`。

算法分两层：
1. **结构切分**：按 `^#{1,6} ` 标题行切出「节」，记录每节的标题路径（如 `# A / ## B`）。
2. **节内切分**：将节内内容先按空行分段；识别并保护 **fenced code block**（``` ``` ```）与 **Markdown 表格**（连续 `|` 行）为原子单元，绝不从中切断。超过 token 上限的原子单元才允许在其内部按断句点续切。

每个最终 chunk 前置其标题路径（`## 章节名` + 正文）。

**替代方案**：`langchain-text-splitters` / `llama-index` 的 `MarkdownHeaderTextSplitter`。**否决**：引入重依赖，且与本项目「手写 scanner、最小依赖」的既有风格冲突；分块逻辑简单可控，手写更易测试。

### 2. Token 计数：轻量估计器（不引 tiktoken）

`doubao` 无离线 tokenizer，且 `tiktoken` 的 cl100k 与 doubao 分词不完全一致。采用估计器：

```
tokens ≈ CJK 字符数（每个 CJK 字符 ≈ 1 token）+ 非 CJK 词数（按空白切分，≈ 1 token/词）
```

在 `chunking.py` 内实现 `estimate_tokens(text)`。默认 `chunk_size=512`（token）、`chunk_overlap=64`（token）。**风险**：估计与真实 token 有 ±20% 偏差；通过 `chunk_size` 保守取值 + 评测兜底（见 Risks）。

### 3. 稀疏侧：pg_trgm + 三元组 GIN + 词项 ILIKE

`vector_store` 新增 `search_sparse(query, node_id, limit)`：
- 建三元组索引：`CREATE INDEX idx_{table}_content_trgm ON {table} USING gin (content gin_trgm_ops)`，并对 `title`/`path` 建同类索引（匹配文件名/标题）。
- 查询前将 query 分词（按空白/标点切 + CJK 逐字散列启发式），每个词项 `w` 生成 `content ILIKE '%w%' OR title ILIKE '%w%' OR path ILIKE '%w%'` 的 OR 并集；命中词项数作为稀疏分数。
- pg_trgm 让 `ILIKE '%...%'` 走 trigram 索引，避免全表扫。

**替代方案**：PG FTS + jieba/zhparser。**否决**：需在 pg 上额外编译安装扩展，部署重；trigram 对「子串 exact 命中」更直接，满足文件名/ID/专有名词召回诉求。

### 4. 稠密侧：去掉 DISTINCT ON，返回 chunk 级 top-N 候选

`search` 的 SQL 移除 `DISTINCT ON (doc_id)`，改为按 chunk 相似度排序，返回候选池 top-N（`candidate_limit=50`），供融合。

### 5. 融合：RRF（k=60）

`search_hybrid(query, limit, node_id)`：
1. `dense = search_dense(query, node_id, candidate_limit)`，对每 chunk 记余弦相似度 `cos_score`。
2. `sparse = search_sparse(query, node_id, candidate_limit)`，记命中词项数。
3. 阈值过滤：`cos_score < min_score` 的 dense 候选丢弃（阈值仅作用于 dense 侧，稀疏 exact 命中不受阈值影响）。
4. 合并两侧排名，按 `RRF(chunk) = Σ 1/(k + rank)` 融合（k=60），rank 取该侧内排名。
5. 同文档 chunk 去重上限：每文档最多返回 `chunks_per_doc=2` 个 chunk（防止单文档霸榜），最终按 RRF 分数取 top-`limit`。

### 6. 相似度阈值

新增配置 `AKM_SEARCH_MIN_SCORE`（默认 `0.2`），作用于 dense 余弦相似度（融合前）。默认值以评测 harness 校准；doubao 归一化情况未知，故先保守，运行后按 `nDCG@10` 调。

### 7. 配置项（新增，`config.py`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AKM_CHUNK_SIZE` | `512` | 分块目标 token 数 |
| `AKM_CHUNK_OVERLAP` | `64` | 块间重叠 token 数 |
| `AKM_SEARCH_MIN_SCORE` | `0.2` | dense 相似度阈值 |
| `AKM_SEARCH_RRF_K` | `60` | RRF 常数 |
| `AKM_SEARCH_CHUNKS_PER_DOC` | `2` | 每文档最多返回 chunk 数 |
| `AKM_SEARCH_CANDIDATE_LIMIT` | `50` | 单侧候选池大小 |

### 8. 评测 harness

在 `src/server/eval/` 新建：
- `dataset.jsonl`：每行 `{"query": str, "relevant_doc_ids": [int], "node_id": str|null}`，小规模手工标注起步（~20 条），后续可替换为真实 query 集。
- `run_eval.py`：读数据集 → 对每条 query 调 `search_hybrid` → 计算 `recall@k`（`|检索到∩相关| / |相关|`）与 `nDCG@10`（分级相关度用二值 0/1）→ 输出均值。
- `baseline.txt` 记录改前基线数字；改后重跑对比。

指标公式与调用入口（直接调 `vector_store.search_hybrid`，绕过 HTTP limit 上限）在脚本内实现，不污染运行时。

## Risks / Trade-offs

- [token 估计偏差] → 保守默认 + 评测校准；若 Ark 提供 token 计数接口，后续替换。
- [trigram 对短词/中文逐字] → 词项 <3 字符时 trigram 命中弱，保留 `similarity()` 兜底；评测覆盖中文文件名/专有名词场景。
- [阈值取值需调] → 阈值仅过滤 dense 侧、稀疏 exact 命中不受影响，且由评测 harness 定量校准。
- [分块算法变更使旧向量失效] → 部署后必须全量重索引（见 Migration）。
- [trigram 索引写入成本] → 三列 GIN 索引增加写放大；知识库写入低频，可接受。
- [同步 psycopg2 阻塞事件循环（既有问题）] → 本次不改，Phase 后续专项处理。

## Migration Plan

1. 第 0 步验证目标 pg 上 `pg_trgm` 扩展可用（`SELECT 1 FROM pg_extension WHERE extname='pg_trgm'`）。
2. `init_table()` 增加 `CREATE EXTENSION IF NOT EXISTS pg_trgm` + content/title/path 三个 trigram 索引；向量表结构不变。
3. 部署后必须全量重索引：调用 `POST /api/rag/index`（分块逻辑已变，旧向量按字符分块，与新分块不兼容），重建 `document_vectors`。
4. 回滚：代码回退 + 重新 `POST /api/rag/index` 重建旧分块向量。

## Open Questions

- doubao 是否有官方 token 计数/批嵌入接口——若有，后续替换估计器并做批量嵌入。
- reranker 具体型号（bge-reranker-v2-m3 候选）——Phase 2 决策。
- 评测数据集的规模扩展方式（合成 vs 人工扩充）——先跑通链路再定。
