"""一次性回填脚本:将历史文档路径中的反斜杠分隔符统一为 `/`.

背景:早期 node 端/本机扫描在 Windows 上使用 ``Path.__str__`` 产生 `\\`
分隔的路径,导致 hub 端 URL 导航、文件树、查找不一致(浏览器会把 URL
中的 `\\` 规范化为 `/`)。自修复起,scanner 与节点入库均已归一化,
本脚本仅负责清洗存量数据。

安全保证:
- 以 (node_id, normalized_path) 为唯一键;若归一化后产生节点内碰撞则中止,
  需人工处理后重跑,绝不静默合并。
- 幂等可重复执行。

用法:
    cd src/server
    uv run python scripts/normalize_document_paths.py
"""

import asyncio
import sys
from pathlib import Path

# 保证可以从任意 CWD 运行
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.document import Document


def norm(path: str) -> str:
    return path.replace("\\", "/").strip()


async def main() -> int:
    engine = create_async_engine(settings.db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(select(Document))
        docs = result.scalars().all()

        by_node: dict[str, dict[str, Document]] = {}
        pending: dict[int, str] = {}  # doc.id -> 归一化路径
        for doc in docs:
            np = norm(doc.path)
            if np == doc.path:
                continue
            if np in by_node.setdefault(doc.node_id, {}):
                print(
                    f"[abort] 节点 {doc.node_id} 归一化路径碰撞: "
                    f"{by_node[doc.node_id][np].path!r} vs {doc.path!r}"
                )
                print("已中止,请人工处理后重跑。")
                return 1
            by_node[doc.node_id][np] = doc
            pending[doc.id] = np

        if not pending:
            print("无需修正:所有路径已是 / 分隔。")
            return 0

        print(f"待修正 {len(pending)} 条路径…")
        for doc in docs:
            np = pending.get(doc.id)
            if np:
                old = doc.path
                doc.path = np
                print(f"  {old!r} -> {np!r}")
        await session.commit()
        print(f"完成:已归一化 {len(pending)} 条。")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))