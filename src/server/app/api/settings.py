"""应用设置 API(RAG 同步模式)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy import select

from app.db import get_session, async_session
from app.models.document import Document
from app.services.auth import require_auth
from app.services.rag.sync import (
    DEFAULT_RAG_MODE,
    VALID_RAG_MODES,
    get_rag_mode,
    set_rag_mode,
    sync_index_and_mark,
)

router = APIRouter()


class SettingsUpdate(BaseModel):
    rag_sync_mode: str


async def _schedule_backfill(session, background_tasks: BackgroundTasks) -> None:
    """切回 auto:后台补齐所有非 excluded 且有内容的文档向量(失败仅告警)."""
    result = await session.execute(
        select(Document.id, Document.title, Document.path, Document.content,
               Document.node_id, Document.rag_status)
        .where(Document.rag_status != "excluded", Document.content.is_not(None))
    )
    upserts = []
    for row in result.all():
        upserts.append({
            "doc_id": row[0], "title": row[1], "path": row[2],
            "content": row[3], "node_id": row[4],
            "pending": row[5] == "pending",
        })
    if upserts:
        background_tasks.add_task(sync_index_and_mark, upserts, [])


@router.get("")
async def get_settings(
    principal=Depends(require_auth("viewer")),
    session=Depends(get_session),
):
    """读取设置(只读)."""
    return {"rag_sync_mode": await get_rag_mode(session)}


@router.put("")
async def put_settings(
    body: SettingsUpdate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session=Depends(get_session),
):
    """更新设置(admin).manual 切换不清向量;切回 auto 后台补齐非 excluded 文档."""
    mode = body.rag_sync_mode
    if mode not in VALID_RAG_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"非法 rag_sync_mode:{mode},合法值 {VALID_RAG_MODES}",
        )
    old = await get_rag_mode(session)
    await set_rag_mode(session, mode)
    if old != mode and mode == "auto":
        await _schedule_backfill(session, background_tasks)
    return {"rag_sync_mode": mode}