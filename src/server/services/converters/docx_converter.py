"""Word (docx) 转 Markdown 转换器.

使用 python-docx 读取 Word 文档并转换为 Markdown。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_docx(file_path: str | Path) -> dict:
    """将 Word 文档转换为 Markdown.

    Args:
        file_path: Word 文件路径

    Returns:
        转换结果 {"title": str, "content": str}
    """
    try:
        from docx import Document
        from docx.document import Document as DocumentType

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        doc = Document(str(file_path))

        # 提取标题
        title = file_path.stem
        if doc.paragraphs and doc.paragraphs[0].style.name.startswith("Heading"):
            title = doc.paragraphs[0].text.strip()

        # 转换内容
        md_lines = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                md_lines.append("")
                continue

            # 处理标题样式
            style_name = para.style.name
            if style_name.startswith("Heading"):
                level = int(style_name.replace("Heading", "").strip() or "1")
                md_lines.append(f"{'#' * level} {text}")
            elif style_name == "List Bullet":
                md_lines.append(f"- {text}")
            elif style_name == "List Number":
                md_lines.append(f"1. {text}")
            else:
                # 处理内联格式
                formatted_text = _format_runs(para)
                md_lines.append(formatted_text)

        # 处理表格
        for table in doc.tables:
            md_lines.append("")
            md_lines.append(_convert_table(table))
            md_lines.append("")

        content = "\n".join(md_lines)

        return {
            "title": title,
            "content": content,
            "source": str(file_path),
        }

    except Exception as e:
        logger.error(f"DOCX conversion error: {e}")
        raise


def _format_runs(paragraph) -> str:
    """处理段落中的内联格式（加粗、斜体等）."""
    parts = []
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue

        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"

        if run.underline:
            text = f"<u>{text}</u>"

        parts.append(text)

    return "".join(parts)


def _convert_table(table) -> str:
    """将 Word 表格转换为 Markdown 表格."""
    rows = []

    # 表头
    header_cells = [cell.text.strip() for cell in table.rows[0].cells]
    rows.append("| " + " | ".join(header_cells) + " |")
    rows.append("| " + " | ".join(["---"] * len(header_cells)) + " |")

    # 数据行
    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)
