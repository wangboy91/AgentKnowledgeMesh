"""同步快照持久化(hash-first 增量同步的状态基础).

记录上次确认同步成功的 {path: hash} 集合,存于 sync_state.json
(开发仓为节点 data 目录,安装版为 ~/.akm-node/,见 DEFAULT_SNAPSHOT_PATH)。
读取失败(文件缺失/损坏/格式不对)一律按空快照处理,触发全量重建自愈;
写入采用临时文件 + replace 原子替换,避免进程中断留下半写状态。
"""

import json
import os
from pathlib import Path

from app.config import BASE_DIR, USER_STATE_DIR

# 默认快照文件位置:
# - 开发仓内已有快照(<node 包>/data/sync_state.json,已 gitignore)时继续用原位置,
#   存量开发状态无感迁移;
# - 否则用用户目录(~/.akm-node/sync_state.json):安装版(uv tool)场景下
#   <node 包> 位于 venv 的 site-packages,升级即丢,会退化为每次全量重扫。
_REPO_SNAPSHOT_PATH = BASE_DIR / "data" / "sync_state.json"


def resolve_snapshot_path(repo_path: Path, user_path: Path) -> Path:
    """选择快照位置:开发仓已有快照用原位置,否则用户目录(安装版)."""
    return repo_path if repo_path.exists() else user_path


DEFAULT_SNAPSHOT_PATH = resolve_snapshot_path(
    _REPO_SNAPSHOT_PATH, USER_STATE_DIR / "sync_state.json"
)


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
