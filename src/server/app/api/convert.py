"""文档转换 API.

支持将 PDF、Word、HTML 等格式转换为 Markdown 并保存到知识库。
"""

import logging
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.auth import require_auth
from app.services.converters import convert_pdf, convert_docx, convert_html, convert_url

logger = logging.getLogger(__name__)

router = APIRouter()


class UrlRequest(BaseModel):
    url: str


class ConvertResponse(BaseModel):
    title: str
    path: str
    size: int
    message: str


@router.post("/upload", response_model=ConvertResponse)
async def upload_and_convert(
    file: UploadFile = File(...),
    principal=Depends(require_auth("admin")),
):
    """上传文件并转换为 Markdown.

    支持格式：PDF, DOCX, HTML
    """
    # 检查文件类型
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()

    if suffix not in [".pdf", ".docx", ".doc", ".html", ".htm"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Supported: .pdf, .docx, .html"
        )

    # 保存上传文件到临时目录
    temp_dir = Path("/tmp/agentknowledge_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / filename

    try:
        # 保存文件
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)

        # 转换
        if suffix == ".pdf":
            result = convert_pdf(temp_file)
        elif suffix in [".docx", ".doc"]:
            result = convert_docx(temp_file)
        elif suffix in [".html", ".htm"]:
            result = convert_html(temp_file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # 保存到知识库
        md_content = result["content"]
        title = result.get("title", Path(filename).stem)

        # 生成保存路径
        knowledge_roots = settings.knowledge_paths
        if not knowledge_roots:
            raise HTTPException(status_code=500, detail="No knowledge root configured")

        # 保存到第一个知识库目录
        save_dir = knowledge_roots[0] / "converted"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()[:50]
        md_filename = f"{safe_title}_{timestamp}.md"
        md_path = save_dir / md_filename

        # 写入 Markdown 文件
        md_path.write_text(md_content, encoding="utf-8")

        return ConvertResponse(
            title=title,
            path=str(md_path.relative_to(knowledge_roots[0])),
            size=len(md_content.encode("utf-8")),
            message=f"Converted and saved to {md_path.name}"
        )

    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()


@router.post("/url", response_model=ConvertResponse)
async def convert_from_url(
    request: UrlRequest,
    principal=Depends(require_auth("admin")),
):
    """从 URL 抓取网页并转换为 Markdown."""
    try:
        # 转换
        result = convert_url(request.url)

        # 保存到知识库
        md_content = result["content"]
        title = result.get("title", "Untitled")

        # 生成保存路径
        knowledge_roots = settings.knowledge_paths
        if not knowledge_roots:
            raise HTTPException(status_code=500, detail="No knowledge root configured")

        save_dir = knowledge_roots[0] / "converted"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()[:50]
        md_filename = f"{safe_title}_{timestamp}.md"
        md_path = save_dir / md_filename

        # 写入 Markdown 文件
        md_path.write_text(md_content, encoding="utf-8")

        return ConvertResponse(
            title=title,
            path=str(md_path.relative_to(knowledge_roots[0])),
            size=len(md_content.encode("utf-8")),
            message=f"Converted and saved to {md_path.name}"
        )

    except Exception as e:
        logger.error(f"URL conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
