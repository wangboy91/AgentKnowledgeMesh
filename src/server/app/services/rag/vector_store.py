"""向量存储服务.

使用 PostgreSQL + pgvector 作为向量数据库，支持：
- 文档向量化存储（Markdown 感知分块）
- 混合检索（dense 向量 ⊕ sparse 关键词，RRF 融合）
- 按节点过滤
"""

import logging
import re

import psycopg2
from psycopg2.extras import execute_values

from app.config import settings

logger = logging.getLogger(__name__)

# 数据库连接
_conn = None
# 表是否已初始化（懒加载标记）
_table_ready = False

# 稀疏检索分词：ASCII 词/数字串 或 CJK 连续串
_TERM = re.compile(r"[A-Za-z0-9]+|[一-鿿]+")


def get_conn():
    """获取 PostgreSQL 连接（与主库共用配置，见 Settings.vector_db_conn）."""
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(**settings.vector_db_conn)
        _conn.autocommit = True
        logger.info(
            f"Connected to vector DB: {settings.vector_db_conn['host']}"
            f":{settings.vector_db_conn['port']}/{settings.vector_db_conn['dbname']}"
        )
    return _conn


def _detect_dimension() -> int:
    """确定向量维度.

    优先使用配置的 vector_dimensions（>0），
    否则通过嵌入探测文本自动检测。
    """
    if settings.vector_dimensions > 0:
        return settings.vector_dimensions

    from app.services.rag.embeddings import get_dimension
    return get_dimension()


def init_table():
    """初始化向量表.

    - 表不存在时创建
    - 已存在但维度不匹配（切换了嵌入模型）时自动重建
    - 建 pg_trgm 扩展与三元组 GIN 索引（稀疏检索用；不可用时降级为全表 ILIKE）
    """
    global _table_ready
    conn = get_conn()
    table = settings.vector_db_table
    dim = _detect_dimension()

    with conn.cursor() as cur:
        # 确保 pgvector 扩展已安装
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # 检查表是否存在
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        )
        table_exists = cur.fetchone() is not None

        if table_exists:
            # 检查现有 embedding 列的维度
            cur.execute(
                """SELECT format_type(a.atttypid, a.atttypmod)
                   FROM pg_attribute a
                   WHERE a.attrelid = %s::regclass AND a.attname = 'embedding'""",
                (table,),
            )
            row = cur.fetchone()
            if row and f"({dim})" not in row[0]:
                # 维度不匹配，模型已切换，旧向量不兼容，重建表
                logger.warning(
                    f"Vector dimension mismatch (existing {row[0]}, need {dim}), "
                    f"recreating table '{table}'"
                )
                cur.execute(f"DROP TABLE {table}")
                table_exists = False

        if not table_exists:
            cur.execute(f"""
                CREATE TABLE {table} (
                    id TEXT PRIMARY KEY,
                    doc_id INTEGER NOT NULL,
                    title TEXT,
                    path TEXT,
                    node_id TEXT,
                    chunk_index INTEGER,
                    total_chunks INTEGER,
                    content TEXT,
                    embedding vector({dim})
                );
            """)

        # doc_id 索引
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_doc_id
            ON {table} (doc_id);
        """)

        # 向量相似度索引（HNSW）
        # 注意：pgvector HNSW 索引上限 2000 维，超过时使用 halfvec 表达式索引（上限 4000 维）
        try:
            if dim <= 2000:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_embedding
                    ON {table} USING hnsw (embedding vector_cosine_ops);
                """)
            else:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_embedding
                    ON {table} USING hnsw ((embedding::halfvec({dim})) halfvec_cosine_ops);
                """)
        except Exception as e:
            logger.warning(f"Vector index creation deferred: {e}")

        # pg_trgm 三元组索引（稀疏检索的关键词精确命中）
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            for col in ("content", "title", "path"):
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_{col}_trgm
                    ON {table} USING gin ({col} gin_trgm_ops);
                """)
        except Exception as e:
            logger.warning(
                f"pg_trgm/trigram index unavailable, sparse search falls back to full scan: {e}"
            )

    _table_ready = True
    logger.info(f"Vector table '{table}' ready (dim={dim})")


def ensure_table():
    """确保向量表已初始化（懒加载，供各入口调用）."""
    if not _table_ready:
        init_table()


def add_document(doc_id: int, title: str, path: str, content: str,
                 node_id: str, chunk_size: int | None = None):
    """将文档添加到向量存储.

    Args:
        doc_id: 文档 ID
        title: 文档标题
        path: 文档路径
        content: 文档内容
        node_id: 节点 ID
        chunk_size: 分块目标 token 数（None 时用 settings.chunk_size）
    """
    from app.services.rag.chunking import chunk_markdown
    from app.services.rag.embeddings import embed_texts

    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table

    # 先删除该文档的旧向量
    delete_document(doc_id)

    # Markdown 感知分块（token 计数 + 标题前置 + 重叠）
    size = chunk_size if chunk_size is not None else settings.chunk_size
    chunks = chunk_markdown(content, chunk_size=size, chunk_overlap=settings.chunk_overlap)
    if not chunks:
        return

    # 生成向量
    embeddings = embed_texts(chunks)

    # 构建数据
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        row_id = f"doc_{doc_id}_chunk_{i}"
        # pgvector 接受字符串格式 '[1.0, 2.0, ...]'
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        rows.append((row_id, doc_id, title, path, node_id, i, len(chunks), chunk, emb_str))

    # 批量插入
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""INSERT INTO {table}
                (id, doc_id, title, path, node_id, chunk_index, total_chunks, content, embedding)
                VALUES %s""",
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)",
        )

    logger.debug(f"Added {len(chunks)} chunks for doc {doc_id}")


def delete_document(doc_id: int):
    """删除文档的所有向量."""
    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table

    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE doc_id = %s", (doc_id,))
        deleted = cur.rowcount
        if deleted > 0:
            logger.debug(f"Deleted {deleted} chunks for doc {doc_id}")


def get_indexed_doc_ids() -> set[int]:
    """返回向量表中已存在的文档 id 集合（回填脚本「只补缺」判断用）."""
    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table

    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT doc_id FROM {table}")
        return {row[0] for row in cur.fetchall()}


def _row_to_result(row) -> dict:
    """将查询行转换为结果 dict."""
    return {
        "doc_id": row[0],
        "title": row[1],
        "path": row[2],
        "node_id": row[3],
        "chunk": row[4],
        "score": float(row[5]),
    }


def search_dense(query: str, node_id: str | None = None,
                 candidate_limit: int | None = None) -> list[dict]:
    """稠密检索：pgvector 余弦相似度，chunk 级 top-N 候选（不按文档去重）."""
    from app.services.rag.embeddings import embed_text, get_dimension

    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table
    limit = candidate_limit or settings.search_candidate_limit

    query_embedding = embed_text(query)
    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # 距离表达式：与索引保持一致
    if get_dimension() > 2000:
        dist_expr = "embedding::halfvec <=> %s::halfvec"
    else:
        dist_expr = "embedding <=> %s::vector"

    where_clause = ""
    params = [emb_str]
    if node_id:
        where_clause = "WHERE node_id = %s"
        params.append(node_id)

    sql = f"""
        SELECT doc_id, title, path, node_id, content, 1 - ({dist_expr}) AS score
        FROM {table}
        {where_clause}
        ORDER BY score DESC
        LIMIT %s
    """
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_row_to_result(r) for r in rows]


def _tokenize(query: str) -> list[str]:
    """将查询切分为词项，去重保序.

    ASCII 词/数字串按整词保留；CJK 连续串拆成重叠二元组（bi-gram），
    使无分词器的稀疏侧仍能命中中文子串（如「知识工程」→ 知识/识工/工程）。
    """
    terms = _TERM.findall(query)
    out: list[str] = []
    for t in terms:
        if t.isascii():
            # 单个 ASCII 字符/数字噪声大，丢弃
            if len(t) >= 2:
                out.append(t)
        elif len(t) <= 2:
            out.append(t)
        else:
            out.extend(t[i:i + 2] for i in range(len(t) - 1))
    seen: set[str] = set()
    dedup: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    return dedup


def _like_pattern(term: str) -> str:
    """将词项转为 ILIKE 模式，转义 ``%`` / ``_`` / ``\\``（PostgreSQL 默认反斜杠转义）."""
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def search_sparse(query: str, node_id: str | None = None,
                  candidate_limit: int | None = None) -> list[dict]:
    """稀疏检索：pg_trgm 关键词精确命中（content/title/path），命中词项数打分."""
    terms = _tokenize(query)
    if not terms:
        return []

    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table
    limit = candidate_limit or settings.search_candidate_limit

    # 命中词项数打分：每个词项命中任一字段计 1
    score_parts: list[str] = []
    where_parts: list[str] = []
    params: list[str] = []

    for t in terms:
        score_parts.append(
            "(CASE WHEN content ILIKE %s OR title ILIKE %s OR path ILIKE %s "
            "THEN 1 ELSE 0 END)"
        )
        params.extend([_like_pattern(t)] * 3)

    for t in terms:
        where_parts.append(
            "(content ILIKE %s OR title ILIKE %s OR path ILIKE %s)"
        )
        params.extend([_like_pattern(t)] * 3)

    score_sql = " + ".join(score_parts)
    where_sql = " OR ".join(where_parts)

    node_filter = ""
    if node_id:
        node_filter = "AND node_id = %s"
        params.append(node_id)

    sql = f"""
        SELECT doc_id, title, path, node_id, content, ({score_sql}) AS score
        FROM {table}
        WHERE ({where_sql}) {node_filter}
        ORDER BY score DESC
        LIMIT %s
    """
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_row_to_result(r) for r in rows]


def search_hybrid(query: str, limit: int = 5, node_id: str | None = None) -> list[dict]:
    """混合检索：文档级加权 RRF 融合.

    先对 dense/sparse 各自按「同文档只保留最佳分块」归并出文档级排名，
    再做加权 RRF 融合，避免 chunk 级融合把多分块文档的排名稀释、
    或让单分块文档借噪声反超（见 eval 回归定位）。最终按文档 rrf 顺序
    返回每文档至多 chunks_per_doc 个分块（dense 优先，sparse-only 补充）。
    """
    ensure_table()
    candidate_limit = settings.search_candidate_limit

    dense = search_dense(query, node_id, candidate_limit)
    sparse = search_sparse(query, node_id, candidate_limit)

    # 相似度阈值过滤（仅作用于 dense 侧；sparse 精确命中不受影响）
    min_score = settings.search_min_score
    dense = [d for d in dense if d["score"] >= min_score]

    def _best_per_doc(rows: list[dict]) -> dict[int, dict]:
        """同文档只保留分数最高的分块."""
        best: dict[int, dict] = {}
        for r in rows:
            d = r["doc_id"]
            if d not in best or r["score"] > best[d]["score"]:
                best[d] = r
        return best

    dense_best = _best_per_doc(dense)
    sparse_best = _best_per_doc(sparse)

    dense_ranked = sorted(dense_best.values(), key=lambda x: x["score"], reverse=True)
    sparse_ranked = sorted(sparse_best.values(), key=lambda x: x["score"], reverse=True)

    # 文档级加权 RRF（dense 主导，sparse 温和补充）
    rrf_k = settings.search_rrf_k
    dense_w = settings.search_dense_weight
    sparse_w = settings.search_sparse_weight
    doc_rrf: dict[int, float] = {}
    for rank, r in enumerate(dense_ranked, start=1):
        doc_rrf[r["doc_id"]] = doc_rrf.get(r["doc_id"], 0.0) + dense_w / (rrf_k + rank)
    for rank, r in enumerate(sparse_ranked, start=1):
        doc_rrf[r["doc_id"]] = doc_rrf.get(r["doc_id"], 0.0) + sparse_w / (rrf_k + rank)

    ordered_docs = sorted(doc_rrf.items(), key=lambda x: x[1], reverse=True)

    # 按文档 rrf 顺序，每文档返回至多 chunks_per_doc 个分块
    chunks_per_doc = settings.search_chunks_per_doc
    results: list[dict] = []
    for doc_id, rrf_score in ordered_docs:
        dense_chunks = {r["chunk"] for r in dense if r["doc_id"] == doc_id}
        doc_dense = [r for r in dense if r["doc_id"] == doc_id]
        doc_sparse_only = [
            r for r in sparse
            if r["doc_id"] == doc_id and r["chunk"] not in dense_chunks
        ]
        picked = 0
        for r in doc_dense + doc_sparse_only:
            if picked >= chunks_per_doc or len(results) >= limit:
                break
            out = dict(r)
            out["score"] = round(rrf_score, 6)
            results.append(out)
            picked += 1
        if len(results) >= limit:
            break

    return results


def search(query: str, limit: int = 5, node_id: str | None = None) -> list[dict]:
    """语义搜索入口（向后兼容）：返回混合检索结果."""
    return search_hybrid(query, limit, node_id)


def get_stats() -> dict:
    """获取向量存储统计."""
    conn = get_conn()
    table = settings.vector_db_table

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]

    return {
        "total_chunks": count,
    }
