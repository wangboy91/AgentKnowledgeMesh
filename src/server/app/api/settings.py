"""应用设置 API(向量化总开关 + RAG 同步模式).

两项设置均持久化于 app_settings 表,支持运行时切换、免重启:
- ``vectorization_enabled``(向量化总开关,默认关闭)
- ``rag_sync_mode``(auto / manual,默认 manual)
"""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_session
from app.services.auth import require_auth
from app.services.rag.sync import (
    VALID_RAG_MODES,
    collect_backfill_payload,
    get_rag_mode,
    get_vectorization_enabled,
    set_rag_mode,
    set_vectorization_enabled,
    should_auto_index,
    sync_index_and_mark,
)

router = APIRouter()


class SettingsUpdate(BaseModel):
    """设置更新体:两项均可选,至少提供一项(支持部分更新)."""

    rag_sync_mode: str | None = None
    vectorization_enabled: bool | None = None


def _init_vector_store_sync() -> None:
    """初始化向量库表(阻塞调用,由调用方放入线程池)."""
    from app.services.rag.vector_store import init_table

    init_table()


async def _schedule_backfill(session, background_tasks: BackgroundTasks) -> None:
    """后台补齐所有非 excluded 且有内容的文档(仅「开启 + auto」组合下调用)."""
    payload = await collect_backfill_payload(session)
    if payload:
        background_tasks.add_task(sync_index_and_mark, payload, [])


@router.get("")
async def get_settings(
    principal=Depends(require_auth("viewer")),
    session=Depends(get_session),
):
    """读取设置(只读)."""
    return {
        "rag_sync_mode": await get_rag_mode(session),
        "vectorization_enabled": await get_vectorization_enabled(session),
    }


@router.put("")
async def put_settings(
    body: SettingsUpdate,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session=Depends(get_session),
):
    """更新设置(admin).

    - 开启向量化:先同步初始化向量库,失败返回 500 且**保持关闭**
    - 关闭向量化:仅落库,不清理既有向量(重新开启即可复用)
    - 进入「开启 + auto」组合:后台补齐所有非 excluded 文档
    """
    if body.rag_sync_mode is None and body.vectorization_enabled is None:
        raise HTTPException(
            status_code=400,
            detail="至少提供一项设置(rag_sync_mode / vectorization_enabled)",
        )
    if body.rag_sync_mode is not None and body.rag_sync_mode not in VALID_RAG_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"非法 rag_sync_mode:{body.rag_sync_mode},合法值 {VALID_RAG_MODES}",
        )

    old_mode = await get_rag_mode(session)
    old_enabled = await get_vectorization_enabled(session)
    new_mode = body.rag_sync_mode if body.rag_sync_mode is not None else old_mode
    new_enabled = (
        body.vectorization_enabled if body.vectorization_enabled is not None else old_enabled
    )

    # 开启方向:先确认向量库可用(建表 + 维度探测),失败则不落库
    if new_enabled and not old_enabled:
        try:
            await asyncio.to_thread(_init_vector_store_sync)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"向量库初始化失败,未开启向量化:{e}",
            )

    if body.rag_sync_mode is not None:
        await set_rag_mode(session, new_mode)
    if body.vectorization_enabled is not None:
        await set_vectorization_enabled(session, new_enabled)

    # 由「非开启+auto」进入「开启+auto」时补齐存量未向量化文档
    if should_auto_index(new_mode, new_enabled) and not should_auto_index(old_mode, old_enabled):
        await _schedule_backfill(session, background_tasks)

    return {"rag_sync_mode": new_mode, "vectorization_enabled": new_enabled}
