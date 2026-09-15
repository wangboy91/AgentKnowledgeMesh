"""Node 配置管理."""

import os
import platform
import uuid
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

# 项目根目录（src/node，即 app 包的父目录）
# 开发场景下与用户目录 .env 并存（见 USER_ENV_FILE）
BASE_DIR = Path(__file__).parent.parent

# 用户级配置/凭证文件：uv tool 安装后 BASE_DIR 位于 venv 的 site-packages，
# 升级即丢，因此凭证必须落在用户目录；AKM_NODE_ENV_FILE 可覆盖路径。
# 解析优先级（高→低）：进程环境变量 > USER_ENV_FILE > BASE_DIR/.env（仅开发仓存在）。
USER_ENV_FILE = Path(
    os.environ.get("AKM_NODE_ENV_FILE") or Path.home() / ".akm-node" / ".env"
)

# 用户级运行数据目录（同步快照等）：AKM_NODE_STATE_DIR 可覆盖
USER_STATE_DIR = Path(
    os.environ.get("AKM_NODE_STATE_DIR") or Path.home() / ".akm-node"
)


class NodeSettings(BaseSettings):
    """Node 配置."""

    # Hub 连接
    hub_url: str = Field(
        "ws://localhost:8000/ws",
    )
    hub_api_url: str = Field(
        "http://localhost:8000/api",
    )

    # 节点信息
    node_id: str = Field(
        "",
    )
    node_name: str = Field(
        "",
    )
    # 节点凭证(account-auth):由 `akm-node login` 写入本地 .env
    node_token: str = Field(
        "",
    )

    # 知识库目录
    knowledge_roots: str = Field(
        "",
    )

    # 心跳间隔（秒）
    heartbeat_interval: int = Field(
        30,
    )

    model_config = {
        "env_prefix": "AKM_",
        # 列表后者优先：用户目录文件覆盖开发仓的 src/node/.env
        "env_file": [str(BASE_DIR / ".env"), str(USER_ENV_FILE)],
    }

    def get_node_id(self) -> str:
        """获取或生成节点ID."""
        if self.node_id:
            return self.node_id
        # 基于机器生成唯一ID
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))

    def get_node_name(self) -> str:
        """获取节点名称."""
        if self.node_name:
            return self.node_name
        return platform.node()

    def get_platform(self) -> str:
        """获取平台."""
        return platform.system().lower()

    @property
    def knowledge_paths(self) -> list[Path]:
        """知识库目录列表."""
        if not self.knowledge_roots:
            default = Path.home() / "Knowledge"
            if default.exists():
                return [default]
            return []

        paths = []
        for root in self.knowledge_roots.split(","):
            root = root.strip()
            if root:
                path = Path(root).expanduser()
                if path.exists():
                    paths.append(path)
        return paths


settings = NodeSettings()
