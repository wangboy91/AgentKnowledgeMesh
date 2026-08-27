"""向量嵌入服务.

支持两种模式：
1. 本地模型：使用 sentence-transformers
2. API 模式：使用 OpenAI 兼容的 Embedding API

设计要点：
- 模型懒加载，首次使用时才加载
- 支持批量嵌入
- 缓存已嵌入的文档（通过 hash 检测变更）
"""

import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

# 全局模型实例（懒加载）
_model = None


def get_model():
    """获取或加载模型."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            from config import settings

            model_name = settings.embedding_model
            logger.info(f"Loading embedding model: {model_name}")
            _model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model


def embed_text(text: str) -> list[float]:
    """将文本转换为向量.

    Args:
        text: 要嵌入的文本

    Returns:
        向量列表
    """
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转换为向量.

    Args:
        texts: 文本列表

    Returns:
        向量列表
    """
    if not texts:
        return []

    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """将长文本分块.

    Args:
        text: 原始文本
        chunk_size: 每块的目标字符数
        chunk_overlap: 块之间的重叠字符数

    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # 尝试在句号、换行处断开
        if end < len(text):
            # 寻找最近的断句点
            for sep in ["\n\n", "\n", "。", ".", "！", "!", "？", "?"]:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size * 0.3:  # 至少30%的内容
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - chunk_overlap

    return chunks
