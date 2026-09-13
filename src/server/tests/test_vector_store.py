"""混合检索逻辑单元测试.

覆盖：分词 / ILIKE 转义 / 相似度阈值过滤 / 多 chunk 去重上限 / RRF 融合。
纯函数与 search_hybrid 的融合逻辑不依赖真实数据库（search_dense/sparse 用桩替换）。
"""

from app.services.rag.vector_store import _like_pattern, _tokenize


class _FakeCursor:
    """记录 execute 语句并返回预设行的假游标."""

    def __init__(self, rows):
        self._rows = rows
        self.executed = None

    def execute(self, sql, params=None):
        self.executed = sql

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeConn:
    def __init__(self, cur):
        self._cur = cur

    def cursor(self):
        return self._cur


def test_get_indexed_doc_ids_dedups(monkeypatch):
    from app.services.rag import vector_store

    cur = _FakeCursor([(1,), (2,), (2,), (3,)])
    monkeypatch.setattr(vector_store, "ensure_table", lambda: None)
    monkeypatch.setattr(vector_store, "get_conn", lambda: _FakeConn(cur))

    assert vector_store.get_indexed_doc_ids() == {1, 2, 3}
    assert "SELECT DISTINCT doc_id FROM" in cur.executed


def test_tokenize_ascii_and_cjk():
    assert _tokenize("hello world") == ["hello", "world"]
    assert _tokenize("文件名 abc123") == ["文件", "件名", "abc123"]
    assert _tokenize("ID-123") == ["ID", "123"]


def test_tokenize_cjk_bigram():
    # 3 字及以上中文串拆成重叠二元组，使稀疏侧能命中中文子串
    assert _tokenize("知识工程") == ["知识", "识工", "工程"]
    # 2 字以内保持整词
    assert _tokenize("核心") == ["核心"]


def test_tokenize_drops_single_ascii():
    assert _tokenize("a b c") == []
    assert _tokenize("x") == []


def test_tokenize_dedup_preserves_order():
    assert _tokenize("foo foo bar") == ["foo", "bar"]


def test_like_pattern_escapes_wildcards():
    assert _like_pattern("my_file") == "%my\\_file%"
    assert _like_pattern("100%") == "%100\\%%"
    assert _like_pattern("a\\b") == "%a\\\\b%"


def _mk(chunk, doc_id, score):
    return {
        "doc_id": doc_id,
        "title": "",
        "path": "",
        "node_id": "",
        "chunk": chunk,
        "score": score,
    }


def test_search_hybrid_threshold_filters_low_dense(monkeypatch):
    from app.config import settings
    from app.services.rag import vector_store

    monkeypatch.setattr(settings, "search_min_score", 0.2)

    def fake_dense(query, node_id=None, candidate_limit=None, excluded_doc_ids=None):
        return [_mk("low", 9, 0.05)]

    def fake_sparse(query, node_id=None, candidate_limit=None, excluded_doc_ids=None):
        return []

    monkeypatch.setattr(vector_store, "ensure_table", lambda: None)
    monkeypatch.setattr(vector_store, "search_dense", fake_dense)
    monkeypatch.setattr(vector_store, "search_sparse", fake_sparse)

    assert vector_store.search_hybrid("q", limit=5) == []


def test_search_hybrid_multi_chunk_and_rrf(monkeypatch):
    from app.config import settings
    from app.services.rag import vector_store

    monkeypatch.setattr(settings, "search_min_score", 0.2)
    monkeypatch.setattr(settings, "search_rrf_k", 60)
    monkeypatch.setattr(settings, "search_chunks_per_doc", 2)
    monkeypatch.setattr(settings, "search_candidate_limit", 50)

    def fake_dense(query, node_id=None, candidate_limit=None, excluded_doc_ids=None):
        return [
            _mk("c1", 1, 0.9),
            _mk("c2", 2, 0.5),
            _mk("c1b", 1, 0.1),  # 低于阈值，dense 侧被过滤
        ]

    def fake_sparse(query, node_id=None, candidate_limit=None, excluded_doc_ids=None):
        return [
            _mk("c1b", 1, 2),  # sparse 精确命中把 c1b 捞回
            _mk("c3", 3, 1),
        ]

    monkeypatch.setattr(vector_store, "ensure_table", lambda: None)
    monkeypatch.setattr(vector_store, "search_dense", fake_dense)
    monkeypatch.setattr(vector_store, "search_sparse", fake_sparse)

    results = vector_store.search_hybrid("q", limit=5)

    # 同文档多 chunk：doc 1 的 c1（dense）与 c1b（sparse）均出现
    doc1_chunks = {r["chunk"] for r in results if r["doc_id"] == 1}
    assert doc1_chunks == {"c1", "c1b"}
    # c3 通过 sparse 进入结果
    assert any(r["doc_id"] == 3 for r in results)
    # c1 与 c1b 均排在前（RRF 分数相同，先 dense 后 sparse）
    assert results[0]["chunk"] in ("c1", "c1b")
