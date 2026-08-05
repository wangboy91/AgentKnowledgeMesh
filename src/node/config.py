"""Node 配置管理."""

import platform
import uuid
from pathlib import Path
from pydantic_settings import BaseSettings


class NodeSettings(BaseSettings):
    """Node 配置."""

    # Hub 连接
    hub_url: str = "ws://localhost:8000/ws"
    hub_api_url: str = "http://localhost:8000/api"

    # 节点信息
    node_id: str = ""
    node_name: str = ""

    # 知识库目录
    knowledge_roots: str = ""

    # 心跳间隔（秒）
    heartbeat_interval: int = 30

    model_config = {
        "env_prefix": "AV_",
        "env_file": ".env",
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
