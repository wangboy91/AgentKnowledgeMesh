"""RAG 子域：向量嵌入与向量存储.

供应商可通过 AKM_EMBEDDING_PROVIDER 切换（ark / local），
向量存储使用 PostgreSQL + pgvector。
"""

from app.services.rag.embeddings import (
    embed_text,
    embed_texts,
    get_dimension,
)
from app.services.rag.chunking import (
    chunk_markdown,
    estimate_tokens,
)
from app.services.rag import vector_store

__all__ = [
    "chunk_markdown",
    "estimate_tokens",
    "embed_text",
    "embed_texts",
    "get_dimension",
    "vector_store",
]
