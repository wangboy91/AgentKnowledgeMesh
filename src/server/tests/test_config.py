"""配置项测试：分块与混合检索配置的默认值与环境变量覆盖."""

from app.config import Settings


def _clear(monkeypatch):
    for name in (
        "AKM_CHUNK_SIZE", "AKM_CHUNK_OVERLAP",
        "AKM_SEARCH_MIN_SCORE", "AKM_SEARCH_RRF_K",
        "AKM_SEARCH_CHUNKS_PER_DOC", "AKM_SEARCH_CANDIDATE_LIMIT",
        "AKM_SEARCH_DENSE_WEIGHT", "AKM_SEARCH_SPARSE_WEIGHT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_chunk_and_search_defaults(monkeypatch):
    _clear(monkeypatch)
    s = Settings(_env_file=None)
    assert s.chunk_size == 512
    assert s.chunk_overlap == 64
    assert s.search_min_score == 0.2
    assert s.search_rrf_k == 60
    assert s.search_chunks_per_doc == 2
    assert s.search_candidate_limit == 50
    assert s.search_dense_weight == 1.0
    assert s.search_sparse_weight == 0.3


def test_chunk_and_search_env_override(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("AKM_CHUNK_SIZE", "256")
    monkeypatch.setenv("AKM_SEARCH_MIN_SCORE", "0.5")
    monkeypatch.setenv("AKM_SEARCH_CHUNKS_PER_DOC", "3")
    monkeypatch.setenv("AKM_SEARCH_SPARSE_WEIGHT", "0.1")
    s = Settings(_env_file=None)
    assert s.chunk_size == 256
    assert s.search_min_score == 0.5
    assert s.search_chunks_per_doc == 3
    assert s.search_sparse_weight == 0.1
