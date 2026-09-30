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
    # Hub 登录账号(可选,node-env-login):配置齐全时启动即自动换取节点凭证,
    # 免去无人值守环境下的交互登录;已有 node_token 时以 token 为准(不触发登录)
    hub_username: str = Field(
        "",
    )
    hub_password: str = Field(
        "",
    )

    # 节点信息
    node_id: str = Field(
        "",
    )
    node_name: str = Field(
        "",
    )
    # 节点凭证(account-auth):由 `akm-node login` 或环境变量账号自动登录写入本地 .env
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

    # 文件变更监听与定时对账（add-node-file-watch）：
    # 监听负责实时（低延迟），对账负责最终一致（兜底监听丢事件的场景）。
    watch_enabled: bool = Field(
        True,
    )
    # 事件防抖窗口（秒）：编辑器保存/git checkout/批量复制会产出密集事件，
    # 聚合后再触发一次同步
    watch_debounce_seconds: float = Field(
        3.0,
    )
    # 定时全量对账间隔（秒）；0 表示关闭对账（仅靠监听，接受丢事件风险）
    watch_reconcile_seconds: int = Field(
        300,
    )
    # 在内置排除目录之外追加的排除目录名（逗号分隔）
    watch_exclude: str = Field(
        "",
    )

    # 上传分批（node-upload-batching）：
    # 单轮待推送文档超量时按体积/条数切分为多个请求，避免单个请求体
    # 撞上对端反向代理的 body 上限（nginx 默认 client_max_body_size 1m）而 413。
    # 注意：此处是**保守估算**的体积口径，真实序列化后可能略小，故默认值
    # 留了余量（见 design.md D2/D3）。
    # 单请求体体积上限（字节）；<= 0 表示该维度不限制
    upload_batch_bytes: int = Field(
        512 * 1024,
    )
    # 单请求文档条数上限；<= 0 表示该维度不限制
    upload_batch_docs: int = Field(
        50,
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
    def has_hub_credentials(self) -> bool:
        """是否配置了完整的 Hub 登录账号(node-env-login).

        两个都填才算配置齐全:只填一个通常是误配置,按"未配置"处理,
        让启动提示引导用户补齐(而非拿半个凭证去撞 401)。
        """
        return bool(self.hub_username and self.hub_password)

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

    @property
    def watch_excluded_names(self) -> set[str]:
        """追加的排除目录名(逗号分隔);内置规则见 akm_shared.is_watchable_markdown."""
        return {name.strip() for name in self.watch_exclude.split(",") if name.strip()}


settings = NodeSettings()
