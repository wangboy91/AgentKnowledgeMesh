"""HTML 转 Markdown 转换器.

使用 BeautifulSoup 解析 HTML 并转换为 Markdown。
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_html(file_path: str | Path) -> dict:
    """将 HTML 文件转换为 Markdown.

    Args:
        file_path: HTML 文件路径

    Returns:
        转换结果 {"title": str, "content": str}
    """
    try:
        from bs4 import BeautifulSoup

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 读取 HTML
        html_content = file_path.read_text(encoding="utf-8")

        return convert_html_string(html_content, source=str(file_path))

    except Exception as e:
        logger.error(f"HTML conversion error: {e}")
        raise


def convert_html_string(html_content: str, source: str = "") -> dict:
    """将 HTML 字符串转换为 Markdown.

    Args:
        html_content: HTML 内容
        source: 来源标识

    Returns:
        转换结果 {"title": str, "content": str}
    """
    try:
        from bs4 import BeautifulSoup, NavigableString, Tag

        soup = BeautifulSoup(html_content, "html.parser")

        # 提取标题
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.text.strip()

        # 如果没有 title，尝试 h1
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.text.strip()

        # 转换主体内容
        # 优先找 article、main、body
        body = soup.find("article") or soup.find("main") or soup.find("body") or soup

        md_content = _convert_element(body)

        return {
            "title": title or "Untitled",
            "content": md_content,
            "source": source,
        }

    except Exception as e:
        logger.error(f"HTML string conversion error: {e}")
        raise


def _convert_element(element) -> str:
    """递归转换 HTML 元素为 Markdown."""
    from bs4 import NavigableString, Tag

    if isinstance(element, NavigableString):
        return str(element)

    if not isinstance(element, Tag):
        return ""

    tag = element.name
    text = ""

    # 处理块级元素
    if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        level = int(tag[1])
        content = _get_text_content(element).strip()
        if content:
            text = f"\n\n{'#' * level} {content}\n\n"

    elif tag == "p":
        content = _get_text_content(element).strip()
        if content:
            text = f"\n\n{content}\n\n"

    elif tag == "br":
        text = "\n"

    elif tag == "hr":
        text = "\n\n---\n\n"

    elif tag in ["ul", "ol"]:
        items = []
        for i, li in enumerate(element.find_all("li", recursive=False)):
            item_text = _get_text_content(li).strip()
            if tag == "ol":
                items.append(f"{i + 1}. {item_text}")
            else:
                items.append(f"- {item_text}")
        text = "\n\n" + "\n".join(items) + "\n\n"

    elif tag == "blockquote":
        content = _get_text_content(element).strip()
        if content:
            lines = content.split("\n")
            text = "\n\n" + "\n".join(f"> {line}" for line in lines) + "\n\n"

    elif tag == "pre":
        code = element.get_text()
        text = f"\n\n```\n{code}\n```\n\n"

    elif tag == "code":
        # 行内代码
        if element.parent.name != "pre":
            text = f"`{element.get_text()}`"

    elif tag == "a":
        href = element.get("href", "")
        link_text = _get_text_content(element).strip()
        if href and link_text:
            text = f"[{link_text}]({href})"
        else:
            text = link_text

    elif tag == "img":
        alt = element.get("alt", "")
        src = element.get("src", "")
        if src:
            text = f"![{alt}]({src})"

    elif tag in ["strong", "b"]:
        content = _get_text_content(element).strip()
        if content:
            text = f"**{content}**"

    elif tag in ["em", "i"]:
        content = _get_text_content(element).strip()
        if content:
            text = f"*{content}*"

    elif tag == "table":
        text = _convert_html_table(element)

    else:
        # 递归处理子元素
        for child in element.children:
            text += _convert_element(child)

    return text


def _get_text_content(element) -> str:
    """获取元素的文本内容，保留内联格式."""
    from bs4 import NavigableString, Tag

    parts = []
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            parts.append(_convert_element(child))
    return "".join(parts)


def _convert_html_table(table) -> str:
    """将 HTML 表格转换为 Markdown 表格."""
    rows = []

    # 获取所有行
    all_rows = table.find_all("tr")
    if not all_rows:
        return ""

    # 处理表头
    header_row = all_rows[0]
    header_cells = header_row.find_all(["th", "td"])
    headers = [cell.get_text().strip() for cell in header_cells]

    rows.append("| " + " | ".join(headers) + " |")
    rows.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # 处理数据行
    for row in all_rows[1:]:
        cells = row.find_all("td")
        cell_texts = [cell.get_text().strip() for cell in cells]
        # 确保列数一致
        while len(cell_texts) < len(headers):
            cell_texts.append("")
        rows.append("| " + " | ".join(cell_texts[:len(headers)]) + " |")

    return "\n\n" + "\n".join(rows) + "\n\n"
