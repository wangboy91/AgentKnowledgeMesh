"""PDF 转 Markdown 转换器.

使用 pymupdf4llm 将 PDF 转换为 Markdown 格式。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_pdf(file_path: str | Path) -> dict:
    """将 PDF 文件转换为 Markdown.

    Args:
        file_path: PDF 文件路径

    Returns:
        转换结果 {"title": str, "content": str, "pages": int}
    """
    try:
        import pymupdf4llm

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # 转换为 Markdown
        md_content = pymupdf4llm.to_markdown(str(file_path))

        # 提取标题（从文件名或首行）
        title = file_path.stem
        lines = md_content.split("\n")
        for line in lines[:10]:  # 前10行找标题
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # 获取页数
        import pymupdf
        doc = pymupdf.open(str(file_path))
        pages = len(doc)
        doc.close()

        return {
            "title": title,
            "content": md_content,
            "pages": pages,
            "source": str(file_path),
        }

    except Exception as e:
        logger.error(f"PDF conversion error: {e}")
        raise
