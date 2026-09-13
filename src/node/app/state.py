"""同步快照持久化(hash-first 增量同步的状态基础).

记录上次确认同步成功的 {path: hash} 集合,存于节点 data 目录下的
sync_state.json(该目录已 gitignore)。读取失败(文件缺失/损坏/格式
不对)一律按空快照处理,触发全量重建自愈;写入采用临时文件 + replace
原子替换,避免进程中断留下半写状态。
"""

import json
import os
from pathlib import Path

from app.config import BASE_DIR

# 默认快照文件:<node 包>/data/sync_state.json
DEFAULT_SNAPSHOT_PATH = BASE_DIR / "data" / "sync_state.json"


def load_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, str]:
    """读取快照;文件缺失或损坏时返回空快照(自愈)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def save_snapshot(snapshot: dict[str, str], path: Path = DEFAULT_SNAPSHOT_PATH) -> None:
    """原子写入快照(临时文件 + replace),自动创建父目录."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp, path)
