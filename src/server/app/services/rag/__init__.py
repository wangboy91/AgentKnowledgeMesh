"""RAG 子域：向量嵌入与向量存储.

供应商可通过 AV_EMBEDDING_PROVIDER 切换（ark / local），
向量存储使用 PostgreSQL + pgvector。
"""

from app.services.rag.embeddings import (
    chunk_text,
    embed_text,
    embed_texts,
    get_dimension,
)
from app.services.rag import vector_store

__all__ = [
    "chunk_text",
    "embed_text",
    "embed_texts",
    "get_dimension",
    "vector_store",
]
