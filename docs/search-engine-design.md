# AKM 搜索与检索机制 · 算法核心设计（待审核稿）

> 审阅状态：**待审核（v0.1 draft）**
> 用途：梳理当前 RAG 向量化 → 检索 → 评分全链路算法，定位"随便搜索都是 2%"现象，
> 供审核后再确定调优方案。文中所有公式/参数均来自当前代码（见文末文件索引）。

---

## 1. 整体管线

```
  ┌────────── 索引侧(离线/增量) ──────────┐     ┌────────── 检索侧(查询时) ──────────┐
  │ 文档入库(扫描/节点上传)                │     │  query                            │
  │   → rag_status 状态机                 │     │   ├─ dense: 查询向量余弦 top-N     │
  │   → 分块 chunk_markdown               │     │   └─ sparse: bigram ILIKE 命中计数  │
  │   → 嵌入 embed_texts                  │     │   → 文档级加权 RRF 融合             │
  │   → 写入 pgvector HNSW                │     │   → 阈值过滤 / excluded 排除        │
  │   → (搜/加二进制化) trgm GIN 索引      │     │   → 返回 chunk + rrf 分数           │
  └──────────────────────────────────────┘     └────────────────────────────────────┘
```

两个独立入口：`/api/rag/search`（混合检索，UI 搜索栏用）与 `/api/search`（旧关键词 LIKE，走文档表）。本文聚焦 RAG 侧。

---

## 2. 索引侧：向量化机制

### 2.1 文档入库与 RAG 状态机

- 来源：hub 本机扫描（`POST /documents/scan`）、节点推送（`PUT /nodes/{id}/documents`）、文档 API。
- 向量化统一走 `services/rag/sync.py` 的后台通道 `sync_index_and_mark`：先入库再后台嵌入，失败仅告警不影响主流程。
- `rag_status` 状态机：
  - **auto 模式**：入库即 `indexed`（后台嵌入）；勾选"加入 RAG"→ `pending` → 嵌入后回写 `indexed`。
  - **manual 模式**：入库即 `excluded`，不产生向量；"移出 RAG"→ `excluded` + 删向量。
- 检索侧只召回 `indexed`（`_excluded_ids` 过滤 `rag_status != indexed`）。

### 2.2 Markdown 感知分块（`chunking.py`）

默认 `chunk_size=512` token、`chunk_overlap=64`。

- **token 估算启发式** `estimate_tokens`：CJK 字符逐字 1 token，非 CJK 字母/数字词 1 token（无离线 tokenizer，±20% 偏差）。
- **块级解析** `_parse_blocks`：识别标题、围栏代码块、表格（表格分隔行）、段落/列表。
  - 标题不单独成块，而是维护**标题栈**，作为后续块的前置路径（`# A / ## B`）拼进 chunk 文本——让向量携带结构上下文。
  - 代码块/表格**原子保留**，绝不从中切断；超大散文按断句点续切并保留句级重叠。
- 输出：`["# A / ## B\n正文", …]`。

**局限**：标题只以文本形式前置，无独立权重；过于追求"块"结构与 embedding 模型的窗口匹配，但未在检索层利用标题字段。

### 2.3 向量嵌入（`embeddings.py`）

- 多供应商：`ark`（火山引擎 doubao-embedding 系列）／`local`（sentence-transformers）。每文本独立请求（ark multimodal 接口单次单向量）。
- 维度自动探测（首次嵌入），写入表结构；切换模型时 `init_table` 检测维度不匹配自动**重建表**（旧向量废弃需全量重索引）。
- ⚠️ **模型名待核对**：当前 `.env` 为 `AKM_EMBEDDING_MODEL=doubao-embedding-vision`，而 `.env.example`/默认值为 `doubao-embedding-vision-250615`。若模型名不生效，会回落旧维度、相似度分布偏低。这是诊断项之一。

### 2.4 向量存储与索引（`vector_store.py`）

- PostgreSQL + pgvector，表 `document_vectors`：`id, doc_id, title, path, node_id, chunk_index, total_chunks, content, embedding vector(dim)`。
- **稠密索引**：HNSW cosine（dim≤2000；>2000 用 halfvec 表达式索引）。
- **稀疏索引**：pg_trgm GIN（content/title/path 三列），支撑左侧的 ILIKE 子串查询。

---

## 3. 检索侧：召回与评分

### 3.1 稠密检索 `search_dense`

- 查询文本同模型嵌入 → `1 - cosine_distance` 即**余弦相似度**（正规化向量时∈[-1,1]）。
- chunk 级取 top-`candidate_limit`(50)，不按文档去重。
- 分数语义：**真实相似度**。取值随模型质量差异大（doubao 中文相似度常见 0.5~0.9，弱模型可能整体压低）。

### 3.2 稀疏检索 `search_sparse`

- 分词 `_tokenize`：ASCII 词/数字 ≥2 保留整词；CJK 连续串拆**重叠二元组**（bi-gram），如「知识工程」→ 知识/识工/工程。
- 打分：每个词项在 content/title/path **任一字段 ILIKE 命中计 1**，累加 → `score ∈ [0, n_terms]`。
- 使用 pg_trgm GIN（实际可走索引，部署不可用时全表 ILIKE 降级）。

**局限**（都影响"乱搜也有结果"）：
- 无词频、无 IDF：词项出现即命中，高频泛词（查询/知识/意义）对打分没有稀释。
- bigram 子串含"无意义组合"（如「义查」），容易误命中。
- 无位置/字段区分：标题命中与正文命中同分。

### 3.3 混合融合：文档级加权 RRF（`search_hybrid`）

1. dense、sparse 各自按**同文档只保留最佳分块**归并为文档级列表。
2. 文档级加权 RRF：
   ```
   RRF(doc) = Σ_rank  w / (k + rank)
   ```
   - `k = 60`，`dense_w = 1.0`，`sparse_w = 0.3`
   - dense 排名在前（rank 越小贡献越大），sparse 温和补充。
3. 按 RRF 排序，每文档至多返回 `chunks_per_doc`(2) 个分块（dense 优先，sparse-only 补充），最终 `score = rrf`（四舍六入 6 位）。

**关键点：最终对外分数是 RRF 排名分，不是任何一侧的相似度。**

### 3.4 阈值与排除

- `search_min_score = 0.2`：仅作用于 **dense 侧**相似度（`score >= min_score` 才参与融合）；sparse 精确命中不受阈值影响。
- `excluded_doc_ids`：非 `indexed` 文档两侧均排除。

### 3.5 RAG 上下文组装（`/rag/context`）

`limit × chunks_per_doc` 候选 → 按 doc_id 去重取最佳 chunk → 回读文档完整内容注入 prompt。与搜索共用同一套检索评分。

---

## 4. 现状诊断：为什么"随便搜索都是 2%"

**实测**（新代码实例，真实库 34 篇文档，`/api/rag/search`）：

| 查询 | 返回数 | top-5 分数（展示为 %） |
|---|---|---|
| `Agent` | 5 | 0.0210 / 0.0210 / 0.0195 / 0.0195 / 0.0195 → 全部「2%」 |
| `知识` | 5 | 0.0208 / 0.0208 / 0.0205 / 0.0205 / 0.0198 → 全部「2%」 |
| `真实API调用方式` | 5 | 0.020 / 0.020 / 0.020 / 0.020 / 0.019 → 全部「2%」 |
| `xyzqq杂乱无意义查询`（乱搜） | 5 | 0.021 / 0.021 / 0.019 / 0.019 / 0.019 → 全部「2%」 |

### 根因 1：展示的是 RRF 排名分，被前端当成"置信度百分比"

- [SearchBar.tsx:122](src/web/src/components/SearchBar.tsx#L122) `(score * 100).toFixed(0) + '%'`。
- RRF 公式：rank=1 时 dense 贡献 `1/(60+1) ≈ 0.0164`，sparse 贡献 `0.3/61 ≈ 0.0049`，合计 **≈0.0213 → 2%**。
- k=60 是 RRF 论文经典值，但它在小库上把所有分数压到同一量级，且**任何查询的 top 都大约 2%**——分数既不反映相似度，也没有区分度。用户把 2% 解读为"检索质量差"。

### 根因 2：检索本身区分度不足（乱搜也出 5 条）

- **稀疏侧**：布尔 bigram 命中 + 无 IDF → 「乱无/意义/查询」这类泛化 bigram 总能在 34 篇里撞上几条，永远有结果；打分对"命中质量"不敏感。
- **稠密侧**：`min_score=0.2` 门槛下，若 doubao 向量相似度整体偏低（模型名/维度问题或短 chunk 语义表达弱），大量无关 chunk 仍能越过门槛参与融合，刷平分数。
- 两者叠加：**召回层"永远有料"，排序层"永远 2%"**，排序相对质量其实未必很差，但没有任何可解释的分数来暴露它。

### 其它可感知问题（实测附带）

- 同一文档两个 chunk 并列出现在结果里（`chunks_per_doc=2` 且不按 chunk 聚合展示），两行同分同标题，观感重复。
- 乱搜依旧 5 条 → 用户侧已失去"分数可信"。

---

## 5. 优化方向（候选，待审核后选择）

按「低风险高收益 → 中风险 → 高风险」排序，每项给出改动面/风险/建议评测量。

### A. 分数语义化（低风险，强烈建议先行）

- **目标**：让 UI 分数可解释、有区分度。
- 做法：
  1. `search_hybrid` 对外同时返回 `rrf`（排序用）与 `confidence`（展示用）。`confidence` 可取 dense 侧真实相似度（`1 - cosine_dist`），sparse-only 命中给固定高值或基于命中率归一。
  2. 或对 RRF 做单调归一化映射（如 `min(1, rrf * α)` 或线性拉伸到 k 下界），保证 top-1 落在可读区间。
- 风险：低；纯展示层+API 字段扩展，不影响排序。

### B. 融合与阈值参数化（低风险，评估驱动）

- 把 `k`、`dense_w/sparse_w`、`min_score`、`chunks_per_doc` 纳入网格搜索，用 `eval/run_eval.py` 的 recall@k + nDCG@10 回回归。
- 特别核对 `min_score=0.2` 与当前模型相似度分布：若大部分相关对 <0.2，门槛过度误杀；反之门槛形同虚设。

### C. 稀疏检索升级（中风险，收益最大）

- **pg_trgm 相似度替代布尔计数**：利用已建 trgm GIN，用 `similarity(content, term)` / `word_similarity` 打分（基于三元组重叠，天然有"命中程度"），可结合字段权重与词项 IDF 系数。
- **或引入 BM25/tsvector**：对中文需 zhparser/jieba 分词；跨字段 BM25 求和。复杂度高，但"乱搜也出结果"的根本解。
- 字段加权：标题命中 > 正文命中（可先用简单系数，`title_hit * 2`）。
- 泛词抑制：对高频 bigram（查询、知识、方法…）降权或加停用词面。

### D. 稠密侧增强（中风险，需先验证模型）

- 核对/切换文本专用 embedding 模型（`doubao-embedding-vision` vs `-250615`，或纯文本向量模型），确认维度与相似度分布（跑一段分布直方图再决定 min_score）。
- 标题/路径权重：将标题单独嵌入，与正文相似度加权融合。
- 查询扩展/改写：当前无。可后置（P3）。
- 重排序（rerank）：P3 可选，结合 MCP Context API 场景按需引入。

### E. 评估体系建设（贯穿）

- 扩充 `eval/dataset.jsonl` 标注集（覆盖当前 34 篇真实库，含负例）。
- 增加指标：**分数校准度**（相关文档分数与非相关的间隔）、top-k 命中率、以及"乱搜空结果"的预期行为（是否该返回空/低置信）。
- 每次调优都在 eval 与测试套件上回归（现有 `tests/test_vector_store.py` 已覆盖混合检索主路径，需同步更新断言）。

---

## 6. 建议调优路线（提案，等待审核）

| 阶段 | 内容 | 工作量 | 风险 | 前置验证 |
|---|---|---|---|---|
| **P1** | 分数语义化（A）+ 稠密相似度分布实测，校准 `min_score`（B 一部分） | 小 | 低 | /api/rag/search 返回 confidence 字段，UI 改展示 |
| **P2** | 稀疏升级（C）：trgm 相似度 + 字段/词项加权；参数网格 + eval 回归 | 中 | 中 | 扩充标注集 |
| **P3** | 可选：词典/BM25、标题独立向量、查询改写、rerank | 大 | 高 | 视 P2 效果决定 |

P1 即可消除"2%"观感；P2 着力提升排序质量与区分度；P3 为锦上添花。

---

## 附：关键参数表（当前值）

| 参数 | 值 | 说明 |
|---|---|---|
| `chunk_size` | 512 | 每块目标 token |
| `chunk_overlap` | 64 | 块间重叠 token |
| `search_min_score` | 0.2 | dense 侧相似度门槛 |
| `search_rrf_k` | 60 | RRF 常数 |
| `search_chunks_per_doc` | 2 | 每文档最多返回分块 |
| `search_candidate_limit` | 50 | 两侧候选上限 |
| `search_dense_weight` | 1.0 | dense RRF 权重 |
| `search_sparse_weight` | 0.3 | sparse RRF 权重 |
| `embedding_provider` | ark | 火山引擎 |
| `embedding_model` | doubao-embedding-vision | ⚠️ 与示例名不一致，需核对 |

## 附：文件索引

- 检索/融合/存储：`src/server/app/services/rag/vector_store.py`（dense / sparse / hybrid / RRF）
- 分块：`src/server/app/services/rag/chunking.py`
- 嵌入：`src/server/app/services/rag/embeddings.py`
- 索引通道：`src/server/app/services/rag/sync.py`
- 端点：`src/server/app/api/rag.py`、`src/server/app/api/search.py`
- 配置：`src/server/app/config.py`
- 评估：`src/server/eval/run_eval.py`、`src/server/eval/dataset.jsonl`
- UI 展示：`src/web/src/components/SearchBar.tsx`
- 测试：`src/server/tests/test_vector_store.py`