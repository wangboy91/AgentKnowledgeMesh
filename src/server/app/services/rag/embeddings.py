"""向量嵌入服务.

支持多供应商切换（通过 AV_EMBEDDING_PROVIDER 环境变量）：
1. ark: 火山引擎 Ark API（doubao-embedding 系列模型）
2. local: 本地 sentence-transformers 模型

设计要点：
- 供应商抽象，后期可扩展其他供应商（OpenAI / 智谱 / 阿里等）
- 模型懒加载，首次使用时才初始化
- 向量维度自动检测（首次嵌入时确定）
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 缓存的向量维度（首次嵌入后确定）
_dimension: int | None = None


def get_dimension() -> int:
    """获取当前模型的向量维度.

    首次调用会嵌入一个探测文本以确定维度。
    """
    global _dimension
    if _dimension is None:
        probe = embed_text("dimension probe")
        _dimension = len(probe)
        logger.info(f"Detected embedding dimension: {_dimension}")
    return _dimension


# ========== 供应商实现 ==========


def _embed_ark(text: str) -> list[float]:
    """调用火山引擎 Ark multimodal embeddings API.

    注意：该接口一次调用只返回一个 embedding，
    即使 input 数组包含多项也只返回整体一个向量。
    因此每个文本需要单独一次请求。
    """
    if not settings.ark_api_key:
        raise ValueError("AV_ARK_API_KEY 未配置")

    resp = httpx.post(
        f"{settings.ark_base_url}/embeddings/multimodal",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.ark_api_key}",
        },
        json={
            "model": settings.embedding_model,
            "input": [{"type": "text", "text": text}],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()

    # 单输入时 data 是对象: {embedding: [...]}
    # 多输入时 data 是数组: [{embedding: [...]}]
    d = data["data"]
    if isinstance(d, list):
        return d[0]["embedding"]
    return d["embedding"]


# 本地模型实例（懒加载）
_local_model = None


def _get_local_model():
    """获取或加载本地 sentence-transformers 模型."""
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading local embedding model: {settings.embedding_model}")
        _local_model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _local_model


def _embed_local(text: str) -> list[float]:
    """使用本地模型嵌入单个文本."""
    model = _get_local_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


# ========== 统一入口 ==========

_PROVIDERS = {
    "ark": _embed_ark,
    "local": _embed_local,
}


def _get_provider():
    """获取当前供应商的嵌入函数."""
    provider = settings.embedding_provider.lower()
    if provider not in _PROVIDERS:
        raise ValueError(
            f"未知的 embedding provider: {provider}，"
            f"可选值: {', '.join(_PROVIDERS.keys())}"
        )
    return _PROVIDERS[provider]


def embed_text(text: str) -> list[float]:
    """将文本转换为向量（统一入口，按配置分发到供应商）.

    Args:
        text: 要嵌入的文本

    Returns:
        向量列表
    """
    embed = _get_provider()
    return embed(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转换为向量.

    Args:
        texts: 文本列表

    Returns:
        向量列表（与输入顺序一一对应）
    """
    if not texts:
        return []

    embeddings = []
    for text in texts:
        embeddings.append(embed_text(text))
    return embeddings


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
