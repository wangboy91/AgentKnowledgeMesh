"""节点管理 API.

提供节点列表、详情、文档等接口。
"""

import logging
import uuid as uuid_lib
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.node import Node
from app.models.document import Document
from app.services.auth import require_auth
from app.services.rag.sync import get_rag_mode, sync_index_and_mark
from app.services.websocket import manager

logger = logging.getLogger(__name__)

router = APIRouter()


class NodeRegisterRequest(BaseModel):
    """节点接入请求(CLI 登录后调用)."""

    node_name: str
    platform: str = "unknown"
    node_id: Optional[str] = None  # 提供且存在则复用该节点并轮换 token


class NodeUpdateRequest(BaseModel):
    """节点更新请求(目前仅禁用/启用)."""

    disabled: bool


@router.post("/register")
async def register_node(
    body: NodeRegisterRequest,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """节点首次接入:创建或更新节点记录并轮换生成新 token.

    由 `akm-node login` 以管理员 JWT 调用;返回的 token 由节点本地保存。
    """
    node = await session.get(Node, body.node_id) if body.node_id else None
    if node is None:
        node = Node(
            id=body.node_id or str(uuid_lib.uuid4()),
            name=body.node_name,
            platform=body.platform,
            status="offline",
        )
        session.add(node)
    else:
        node.name = body.node_name
        node.platform = body.platform
        node.disabled = False
    node.token = uuid_lib.uuid4().hex  # 每次接入轮换,旧 token 立即失效
    await session.commit()
    await session.refresh(node)
    return {"node_id": node.id, "node_token": node.token, "name": node.name}


class NodeDocumentItem(BaseModel):
    """节点推送的单篇文档.

    content 可选(hash-first 协议):未变更文档仅上报元信息,不带全文。
    """

    path: str
    title: str
    hash: str
    size: int
    content: str | None = None


class NodeDocumentsPayload(BaseModel):
    """节点文档上传请求体.

    deletions 为显式删除列表(hash-first 协议);字段缺省(旧版全量推送)时,
    服务端按"列表缺失即删除"兼容推导。
    """

    documents: list[NodeDocumentItem]
    deletions: list[str] = []


@router.get("")
async def list_nodes(
    principal=Depends(require_auth("viewer")),
    session: AsyncSession = Depends(get_session),
):
    """获取所有节点列表."""
    result = await session.execute(select(Node).order_by(Node.created_at.desc()))
    nodes = result.scalars().all()

    # 在线状态以内存连接管理器为准(双向判定,DB 中的状态仅是上次连接的痕迹)
    online_nodes = manager.get_online_nodes()
    for node in nodes:
        node.status = "online" if node.id in online_nodes else "offline"

    return [node.to_dict() for node in nodes]


@router.get("/{node_id}")
async def get_node(
    node_id: str,
    principal=Depends(require_auth("viewer")),
    session: AsyncSession = Depends(get_session),
):
    """获取节点详情."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 更新在线状态
    node.status = "online" if manager.is_online(node_id) else "offline"

    return node.to_dict()


@router.get("/{node_id}/documents")
async def get_node_documents(
    node_id: str,
    principal=Depends(require_auth("viewer")),
    session: AsyncSession = Depends(get_session),
):
    """获取节点的文档列表."""
    # 检查节点是否存在
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 获取该节点的文档
    result = await session.execute(
        select(Document)
        .where(Document.node_id == node_id)
        .order_by(Document.updated_at.desc())
    )
    documents = result.scalars().all()

    return {
        "node": node.to_dict(),
        "documents": [doc.to_dict(include_content=False) for doc in documents],
    }


async def _sync_node_documents(
    session: AsyncSession,
    node_id: str,
    documents: list[NodeDocumentItem],
    deletions: list[str],
    implicit_delete: bool,
    rag_mode: str,
) -> tuple[dict, dict]:
    """按 (node_id, path) 作用域增量同步文档.

    三分支入库:带全文按 hash 比对插入/更新;无全文且库中 hash 一致忽略;
    无全文且 hash 不一致(或路径不存在)计入 rejected,不入库,由节点
    下轮带全文重传。deletions 显式删除对应文档;implicit_delete(旧版
    全量推送,请求未携带 deletions 字段)时保留"列表缺失即删除"的兼容推导。
    只增删改 node_id 匹配的文档，绝不触及 local 或其他节点的文档。
    返回 (同步统计, 向量操作载荷)；载荷在 commit 前捕获所需数据
    （新增文档 flush 取 id、待删文档删除前取 id），供响应后派发后台向量维护。

    路径归一化:无论节点端(旧版 Windows 扫描)推送 "/" 还是 "\\" 分隔符,
    统一以 "/" 入库——hub 端 URL/树/查找均以此为准,避免跨端路径不一致。
    """
    # 归一化路径(兼容 Windows 节点旧数据;空格两端清理)
    def norm(p: str) -> str:
        return p.replace("\\", "/").strip()

    result = await session.execute(
        select(Document).where(Document.node_id == node_id)
    )
    existing = {norm(doc.path): doc for doc in result.scalars().all()}

    stats = {"created": 0, "updated": 0, "deleted": 0, "rejected": []}
    changed: list[Document] = []
    created_this_batch: set[str] = set()  # 同批内新增路径去重(归一化后可能碰撞)

    for doc in documents:
        path = norm(doc.path)
        if not path:
            continue
        old_doc = existing.get(path)
        if doc.content is None:
            # hash-first:无全文条目仅在库中哈希一致时跳过,否则拒绝等待下轮重传
            if old_doc is not None and old_doc.hash == doc.hash:
                continue
            reason = "path not found" if old_doc is None else "hash mismatch"
            stats["rejected"].append({"path": path, "reason": reason})
            continue
        if old_doc is None and path not in created_this_batch:
            new_doc = Document(
                node_id=node_id,
                path=path,
                title=doc.title,
                hash=doc.hash,
                size=doc.size,
                content=doc.content,
                rag_status="indexed" if rag_mode == "auto" else "excluded",
            )
            session.add(new_doc)
            created_this_batch.add(path)
            stats["created"] += 1
            changed.append(new_doc)
        elif old_doc is not None and old_doc.hash != doc.hash:
            old_doc.title = doc.title
            old_doc.hash = doc.hash
            old_doc.size = doc.size
            old_doc.content = doc.content
            old_doc.rag_status = "indexed" if rag_mode == "auto" else "excluded"
            stats["updated"] += 1
            changed.append(old_doc)

    deleted_ids: list[int] = []
    # bulk delete 前捕获 doc_id（删除后无从查询，向量分块按 doc_id 清理）
    scanned_paths = {norm(doc.path) for doc in documents}
    to_delete: set[str] = {norm(p) for p in deletions if norm(p) in existing}
    if implicit_delete:
        # 旧版全量推送兼容:列表缺失即删除
        to_delete |= set(existing.keys()) - scanned_paths
    if to_delete:
        deleted_ids = [existing[p].id for p in to_delete]
        await session.execute(
            delete(Document).where(
                Document.node_id == node_id,
                Document.path.in_(to_delete),
            )
        )
        stats["deleted"] = len(to_delete)

    # flush 使新增文档获得 id，载荷在 commit 前构建（避免回滚后向量已派发）
    await session.flush()
    upserts = [
        {
            "doc_id": d.id,
            "title": d.title,
            "path": d.path,
            "content": d.content,
            "node_id": d.node_id,
        }
        for d in changed
    ]
    # manual 模式下 new/updated 文档不入向量(rag_status=excluded),仅维持删除清理
    if rag_mode == "manual":
        upserts = []
    await session.commit()
    return stats, {"upserts": upserts, "deleted_ids": deleted_ids}


@router.put("/{node_id}/documents")
async def put_node_documents(
    node_id: str,
    payload: NodeDocumentsPayload,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """接收节点推送的文档并增量入库（作用域限定为该节点）.

    hash-first 协议:请求显式携带 deletions 字段时按显式列表删除、不做
    隐式缺失删除;字段缺省视为旧版全量推送,保留"列表缺失即删除"兼容行为。
    入库成功后在后台维护向量索引（created/updated 嵌入、deleted 清理），
    嵌入耗时与失败均不影响本次同步响应。
    """
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 被禁用的节点拒绝一切上传(401,与令牌无效同语义)
    if node.disabled:
        raise HTTPException(status_code=401, detail="Node is disabled")

    # 校验 Bearer token
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    if not token or token != node.token:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 以"请求是否携带 deletions 字段"区分新旧协议(旧版节点不发该字段)
    implicit_delete = "deletions" not in payload.model_fields_set
    rag_mode = await get_rag_mode(session)
    stats, vector_ops = await _sync_node_documents(
        session, node_id, payload.documents, payload.deletions, implicit_delete, rag_mode,
    )

    # commit 成功后才派发后台向量维护(统一通道,嵌入不阻塞响应)
    if vector_ops["upserts"] or vector_ops["deleted_ids"]:
        background_tasks.add_task(
            sync_index_and_mark, vector_ops["upserts"], vector_ops["deleted_ids"]
        )

    return stats


@router.put("/{node_id}")
async def update_node(
    node_id: str,
    body: NodeUpdateRequest,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """禁用/启用节点(admin):禁用后注册与上传均被拒."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    node.disabled = body.disabled
    await session.commit()
    await session.refresh(node)
    return node.to_dict()


@router.post("/{node_id}/reset-token")
async def reset_node_token(
    node_id: str,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """重置节点 token(admin):生成新 token,旧 token 立即失效."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    node.token = uuid_lib.uuid4().hex
    await session.commit()
    await session.refresh(node)
    return {"node_id": node.id, "node_token": node.token}


@router.post("/{node_id}/sync")
async def sync_node_documents(
    node_id: str,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """请求节点同步文档.

    向在线节点发送同步请求，节点会将文档列表发送回来。
    """
    if not manager.is_online(node_id):
        raise HTTPException(status_code=400, detail="Node is offline")

    # 发送同步请求到节点
    await manager.send_to_node(node_id, {"type": "sync_request"})

    return {"message": "Sync request sent"}


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    background_tasks: BackgroundTasks,
    principal=Depends(require_auth("admin")),
    session: AsyncSession = Depends(get_session),
):
    """删除节点及其所有文档（含向量分块的级联清理）."""
    node = await session.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 删除前捕获文档 id（删除后无从映射向量分块）
    result = await session.execute(
        select(Document.id).where(Document.node_id == node_id)
    )
    doc_ids = [row[0] for row in result.all()]

    # 删除该节点的所有文档
    from sqlalchemy import delete
    await session.execute(delete(Document).where(Document.node_id == node_id))

    # 删除节点
    await session.delete(node)
    await session.commit()

    # 后台级联清理该节点全部文档的向量分块（失败仅告警）
    if doc_ids:
        background_tasks.add_task(sync_index_and_mark, [], doc_ids)

    return {"message": "Node and its documents deleted"}
