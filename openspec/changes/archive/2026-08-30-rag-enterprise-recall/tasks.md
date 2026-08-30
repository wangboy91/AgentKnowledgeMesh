## 1. 前置验证

- [x] 1.1 连接目标 pg 验证 `pg_trgm` 扩展已安装，验证 `SELECT 1 FROM pg_extension WHERE extname='pg_trgm'` 返回一行

## 2. 分块器

- [x] 2.1 在 `src/server/app/services/rag/` 新增 `chunking.py`，实现 `estimate_tokens`（CJK 逐字 + 非 CJK 按词）与 `chunk_markdown`（标题层级切分、空行分段、fenced code block 与表格原子保护、标题前置、token 计数 + 重叠），验证单元测试覆盖标题层级/表格/代码块/短文档单块/token 计数
- [x] 2.2 在 `app/config.py` 新增 `AKM_CHUNK_SIZE`（默认 512）与 `AKM_CHUNK_OVERLAP`（默认 64），验证 `Settings()` 读取默认值与环境变量覆盖
- [x] 2.3 `vector_store.add_document` 改用 `chunk_markdown` 替换旧的 `chunk_text`，验证 `cd src/server && uv run pytest -q` 通过

## 3. 稀疏检索

- [x] 3.1 `vector_store.init_table` 增加 `CREATE EXTENSION IF NOT EXISTS pg_trgm` 及 content/title/path 三个 trigram GIN 索引，验证 psql 查询 `pg_indexes` 确认索引存在
- [x] 3.2 实现 `vector_store.search_sparse(query, node_id, limit)`（分词 + 词项 OR `ILIKE` + 命中词项数打分），验证单元测试对文件名/ID/专有名词的 exact 命中返回预期 chunk

## 4. 混合检索

- [x] 4.1 重构 `vector_store.search` 为 chunk 级 dense 检索：移除 `DISTINCT ON (doc_id)`，返回 top-N 候选（含余弦相似度），验证单元测试确认同文档多 chunk 均进入候选
- [x] 4.2 实现 `vector_store.search_hybrid(query, limit, node_id)`：dense 阈值过滤 + sparse 合并 + RRF（k=60）融合 + 每文档 `chunks_per_doc` 上限 + top-limit，验证单元测试覆盖阈值过滤/多 chunk/RRF 排序
- [x] 4.3 在 `app/config.py` 新增 `AKM_SEARCH_MIN_SCORE`（0.2）/`AKM_SEARCH_RRF_K`（60）/`AKM_SEARCH_CHUNKS_PER_DOC`（2）/`AKM_SEARCH_CANDIDATE_LIMIT`（50），验证 `Settings()` 读取默认值与环境变量覆盖

## 5. API 接线

- [x] 5.1 `api/rag.py` 的 `semantic_search` 改调 `search_hybrid`，返回结构保持 `results`（含 score 与多 chunk），验证集成测试覆盖 limit/node_id 过滤
- [x] 5.2 `api/rag.py` 的 `get_rag_context` 兼容多 chunk 结果（按 doc_id 去重组装完整文档），验证集成测试返回文档不重复

## 6. 评测 harness

- [x] 6.1 新建 `src/server/eval/dataset.jsonl`（约 20 条手工标注 `query/relevant_doc_ids/node_id`），验证脚本可解析且字段合法
- [x] 6.2 新建 `src/server/eval/run_eval.py`，直接调 `search_hybrid` 计算 `recall@k` 与 `nDCG@10` 并输出均值，验证运行脚本输出指标数值
- [x] 6.3 记录改前基线（旧检索）与改后 `recall@k`/`nDCG@10` 对比，验证输出对比表且改后指标不低于基线（recall@5 0.9750=0.9750，nDCG@10 0.9266→0.9622）

## 7. 重索引与文档

- [x] 7.1 部署后执行全量重索引（`POST /api/rag/index`）以重建新分块向量，验证 `/api/rag/stats` 的 `total_chunks` 与文档数一致且无报错（59 文档 → 1509 chunks，0 失败）
- [x] 7.2 更新 `README.md`（新增配置项、检索行为说明、eval 用法），验证文档与实现一致（`.env.example` 同步更新分块与混合检索配置）
