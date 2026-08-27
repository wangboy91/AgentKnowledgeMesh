"""向量存储服务.

使用 ChromaDB 作为向量数据库，支持：
- 文档向量化存储
- 语义搜索
- 按节点过滤
"""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings

from config import settings

logger = logging.getLogger(__name__)

# ChromaDB 客户端实例
_client = None
_collection = None


def get_client() -> chromadb.ClientAPI:
    """获取 ChromaDB 客户端."""
    global _client
    if _client is None:
        # 使用持久化存储
        persist_dir = Path(settings.db_path).parent / "chromadb"
        persist_dir.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        logger.info(f"ChromaDB initialized at {persist_dir}")
    return _client


def get_collection():
    """获取或创建文档集合."""
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )
        logger.info(f"Collection 'documents' ready, count: {_collection.count()}")
    return _collection


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
    from services.embeddings import embed_texts, chunk_text

    collection = get_collection()

    # 先删除该文档的旧向量
    delete_document(doc_id)

    # 分块
    chunks = chunk_text(content, chunk_size=chunk_size)

    if not chunks:
        return

    # 生成向量
    embeddings = embed_texts(chunks)

    # 构建元数据
    ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "title": title,
            "path": path,
            "node_id": node_id,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    # 添加到集合
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.debug(f"Added {len(chunks)} chunks for doc {doc_id}")


def delete_document(doc_id: int):
    """删除文档的所有向量."""
    collection = get_collection()

    # 查找该文档的所有 chunk
    results = collection.get(
        where={"doc_id": doc_id}
    )

    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.debug(f"Deleted {len(results['ids'])} chunks for doc {doc_id}")


def search(query: str, limit: int = 5, node_id: str | None = None) -> list[dict]:
    """语义搜索.

    Args:
        query: 查询文本
        limit: 返回结果数量
        node_id: 可选，按节点过滤

    Returns:
        搜索结果列表
    """
    from services.embeddings import embed_text

    collection = get_collection()

    if collection.count() == 0:
        return []

    # 生成查询向量
    query_embedding = embed_text(query)

    # 构建过滤条件
    where = None
    if node_id:
        where = {"node_id": node_id}

    # 搜索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"]
    )

    # 整理结果
    search_results = []
    seen_docs = set()

    for i, (doc, metadata, distance) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    )):
        doc_id = metadata["doc_id"]

        # 去重：同一文档只返回最相关的 chunk
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)

        search_results.append({
            "doc_id": doc_id,
            "title": metadata["title"],
            "path": metadata["path"],
            "node_id": metadata["node_id"],
            "chunk": doc,
            "score": 1 - distance,  # 转换为相似度分数
        })

    return search_results[:limit]


def get_stats() -> dict:
    """获取向量存储统计."""
    collection = get_collection()
    return {
        "total_chunks": collection.count(),
    }
