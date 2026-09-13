"""Node 配置管理."""

import platform
import uuid
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

# 项目根目录（src/node，即 app 包的父目录）
# 所有相对路径均锚定到此目录，与运行时 CWD 无关
BASE_DIR = Path(__file__).parent.parent


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
        "env_file": str(BASE_DIR / ".env"),
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
