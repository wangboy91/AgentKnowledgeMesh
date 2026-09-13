"""MCP 工具输出格式化(Hub 与节点代理共用).

单一来源保证三接入形态(Hub stdio / Hub SSE / 节点本地代理)的
工具输出一致;输入统一为 REST to_dict 形态的文档字典
(id/node_id/path/title/hash/size/tags/created_at/updated_at[/content])。
"""

from __future__ import annotations


def format_search_results(query: str, documents: list[dict]) -> str:
    """格式化搜索结果(与 Hub MCP 历史输出格式对齐)."""
    if not documents:
        return f"未找到与 '{query}' 相关的文档。"
    lines = [f"找到 {len(documents)} 个相关文档：\n"]
    for doc in documents:
        lines.append(f"## {doc['title']}")
        lines.append(f"- 路径: {doc['path']}")
        lines.append(f"- 节点: {doc['node_id']}")
        lines.append(f"- 大小: {doc['size'] / 1024:.1f} KB")
        lines.append(f"- 更新: {doc['updated_at']}")
        lines.append("")
    return "\n".join(lines)


def format_document_detail(doc: dict) -> str:
    """格式化单篇文档详情(含全文)."""
    return f"""# {doc['title']}

**路径**: {doc['path']}
**节点**: {doc['node_id']}
**大小**: {doc['size'] / 1024:.1f} KB
**更新时间**: {doc['updated_at']}

---

{doc.get('content') or '(空文档)'}
"""


def format_document_list(documents: list[dict]) -> str:
    """格式化文档列表(不含正文)."""
    if not documents:
        return "暂无文档。"
    lines = [f"文档列表（共 {len(documents)} 个）：\n"]
    for doc in documents:
        lines.append(f"- [{doc['id']}] {doc['title']} ({doc['path']})")
    return "\n".join(lines)


def format_semantic_search(query: str, results: list[dict]) -> str:
    """格式化语义检索结果(关键词格式同构,增加分数与命中分块)."""
    if not results:
        return f"未找到与 '{query}' 语义相关的文档。"
    lines = [f"找到 {len(results)} 个语义相关文档：\n"]
    for r in results:
        title = r.get("title") or f"文档 {r['doc_id']}"
        lines.append(f"## {title}")
        lines.append(f"- 路径: {r.get('path', '')}")
        lines.append(f"- 节点: {r.get('node_id', '')}")
        lines.append(f"- 分数: {r['score']:.4f}")
        lines.append("")
        chunk = (r.get("chunk") or "").strip()
        if chunk:
            lines.append(chunk)
            lines.append("")
    return "\n".join(lines)
