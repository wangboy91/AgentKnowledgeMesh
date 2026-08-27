"""向量存储服务.

使用 PostgreSQL + pgvector 作为向量数据库，支持：
- 文档向量化存储
- 语义搜索（余弦相似度）
- 按节点过滤
"""

import logging

import psycopg2
from psycopg2.extras import execute_values

from app.config import settings

logger = logging.getLogger(__name__)

# 数据库连接
_conn = None
# 表是否已初始化（懒加载标记）
_table_ready = False


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

    _table_ready = True
    logger.info(f"Vector table '{table}' ready (dim={dim})")


def ensure_table():
    """确保向量表已初始化（懒加载，供各入口调用）."""
    if not _table_ready:
        init_table()


def add_document(doc_id: int, title: str, path: str, content: str,
                 node_id: str, chunk_size: int = 500):
    """将文档添加到向量存储.

    Args:
        doc_id: 文档 ID
        title: 文档标题
        path: 文档路径
        content: 文档内容
        node_id: 节点 ID
        chunk_size: 分块大小
    """
    from app.services.rag.embeddings import embed_texts, chunk_text

    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table

    # 先删除该文档的旧向量
    delete_document(doc_id)

    # 分块
    chunks = chunk_text(content, chunk_size=chunk_size)
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


def search(query: str, limit: int = 5, node_id: str | None = None) -> list[dict]:
    """语义搜索.

    Args:
        query: 查询文本
        limit: 返回结果数量
        node_id: 可选，按节点过滤

    Returns:
        搜索结果列表
    """
    from app.services.rag.embeddings import embed_text, get_dimension

    ensure_table()
    conn = get_conn()
    table = settings.vector_db_table

    # 生成查询向量
    query_embedding = embed_text(query)
    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # 距离表达式：与索引保持一致
    # pgvector HNSW 上限 2000 维，超过时索引和查询都用 halfvec
    if get_dimension() > 2000:
        dist_expr = "embedding::halfvec <=> %s::halfvec"
    else:
        dist_expr = "embedding <=> %s::vector"

    # 构建查询
    # 使用余弦距离: 1 - cosine_distance = cosine_similarity
    # 子查询取每个文档最高分 chunk，外层按分数排序
    where_clause = ""
    params = [emb_str]

    if node_id:
        where_clause = "WHERE node_id = %s"
        params.append(node_id)

    sql = f"""
        SELECT doc_id, title, path, node_id, content, score FROM (
            SELECT DISTINCT ON (doc_id)
                doc_id, title, path, node_id, content,
                1 - ({dist_expr}) AS score
            FROM {table}
            {where_clause}
            ORDER BY doc_id, score DESC
        ) sub
        ORDER BY score DESC
        LIMIT %s
    """
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "doc_id": row[0],
            "title": row[1],
            "path": row[2],
            "node_id": row[3],
            "chunk": row[4],
            "score": float(row[5]),
        })

    return results


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
