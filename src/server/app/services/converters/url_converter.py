"""URL 转 Markdown 转换器.

抓取网页内容并转换为 Markdown。
"""

import logging
import re

logger = logging.getLogger(__name__)


def convert_url(url: str) -> dict:
    """将网页转换为 Markdown.

    Args:
        url: 网页 URL

    Returns:
        转换结果 {"title": str, "content": str, "url": str}
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        # 抓取网页
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        response.raise_for_status()

        html_content = response.text

        # 使用 HTML 转换器
        from services.converters.html_converter import convert_html_string
        result = convert_html_string(html_content, source=url)

        # 确保有标题
        if not result.get("title") or result["title"] == "Untitled":
            # 从 URL 提取标题
            from urllib.parse import urlparse
            parsed = urlparse(url)
            result["title"] = parsed.path.split("/")[-1] or parsed.netloc

        return result

    except Exception as e:
        logger.error(f"URL conversion error: {e}")
        raise
