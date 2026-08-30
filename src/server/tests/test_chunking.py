"""分块器单元测试.

覆盖：标题层级 / 表格与代码块不切碎 / 标题前置 / token 计数 / 短文档单块。
"""

from app.services.rag.chunking import chunk_markdown, estimate_tokens


def test_estimate_tokens_cjk_and_words():
    """CJK 逐字、非 CJK 按词计数."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好") == 2
    assert estimate_tokens("hello world") == 2
    # 混合：4 个汉字 + 1 个英文词 = 5
    assert estimate_tokens("你好世界 hello") == 5


def test_short_doc_single_chunk():
    """短文档整篇作为单块."""
    text = "一个很短的文档。"
    chunks = chunk_markdown(text, chunk_size=512, chunk_overlap=64)
    assert chunks == [text]


def test_heading_hierarchy_splits_sections():
    """各级标题下内容作为独立 chunk."""
    text = (
        "# 一级标题\n"
        "一级下的内容。\n"
        "## 二级标题\n"
        "二级下的内容。\n"
    )
    chunks = chunk_markdown(text, chunk_size=512, chunk_overlap=64)
    assert len(chunks) == 2
    assert chunks[0].startswith("# 一级标题")
    assert "一级下的内容" in chunks[0]
    assert chunks[1].startswith("# 一级标题 / ## 二级标题")
    assert "二级下的内容" in chunks[1]


def test_table_not_split():
    """表格作为原子单元，不从中切断."""
    rows = ["| 列A | 列B |", "| --- | --- |"]
    rows += [f"| 行{i} | 值{i} |" for i in range(50)]
    text = "# 表格\n\n" + "\n".join(rows) + "\n"
    chunks = chunk_markdown(text, chunk_size=32, chunk_overlap=8)
    # 表格必须完整出现在某个 chunk 中
    table = "\n".join(rows)
    assert any(table in c for c in chunks)


def test_code_block_not_split():
    """fenced code block 作为原子单元，不从中切断."""
    code = "\n".join(["```python"] + [f"x{i} = {i}" for i in range(50)] + ["```"])
    text = "# 代码\n\n" + code + "\n"
    chunks = chunk_markdown(text, chunk_size=32, chunk_overlap=8)
    assert any(code in c for c in chunks)


def test_token_budget_and_overlap():
    """超长散文按 token 续切，块间保留重叠."""
    # 无标题、无空行的长文本，句末用中文句号
    text = "".join(f"第{i}句话包含一些内容用于测试分块。" for i in range(100))
    chunks = chunk_markdown(text, chunk_size=64, chunk_overlap=16)
    assert len(chunks) > 1
    for c in chunks:
        assert estimate_tokens(c) <= 64 + 32  # 允许重叠带来的少量超出
    # 重叠：相邻块末尾与下一块开头存在共享句子片段
    assert chunks[0][-8:] in chunks[1]
