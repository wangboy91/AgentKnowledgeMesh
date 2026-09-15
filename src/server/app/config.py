"""AgentKnowledgeMesh 配置管理."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

# 项目根目录（src/server，即 app 包的父目录）
# 所有相对路径均锚定到此目录，与运行时 CWD 无关
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """应用配置，支持环境变量覆盖."""

    # 服务配置
    app_name: str = Field(
        "AgentKnowledgeMesh",
    )
    # 鉴权配置(account-auth)
    secret_key: str = Field(
        "",
    )  # JWT 密钥;为空时首次启动生成并持久化到 data/secret.key
    admin_username: str = Field(
        "",
    )  # 首次启动创建的管理员用户名(空则默认 admin)
    admin_password: str = Field(
        "",
    )  # 首次启动创建的管理员密码(空则生成随机密码打印到日志)
    app_version: str = Field(
        "0.2.0",
    )
    host: str = Field(
        "0.0.0.0",
    )
    port: int = Field(
        8000,
    )
    debug: bool = Field(
        False,
    )

    # 数据库配置
    # 类型: sqlite / postgres
    db_type: str = Field(
        "sqlite",
    )

    # SQLite 配置（锚定到项目根目录，Docker 中通过 AKM_DB_PATH 覆盖）
    db_path: str = Field(
        str(BASE_DIR / "data" / "agentvault.db"),
    )

    # PostgreSQL 配置
    db_host: str = Field(
        "localhost",
    )
    db_port: int = Field(
        5432,
    )
    db_name: str = Field(
        "agentvault",
    )
    db_user: str = Field(
        "postgres",
    )
    db_password: str = Field(
        "",
    )

    # 知识库根目录，支持多个目录用逗号分隔
    # 例如: "/Users/me/obsidian-doc,/Users/me/projects/docs"
    knowledge_roots: str = Field(
        "",
    )

    # 扫描配置
    scan_extensions: list[str] = Field(
        [".md"],
    )
    max_file_size_mb: int = Field(
        10,
    )

    # 向量嵌入配置（支持多供应商切换）
    # 供应商: ark (火山引擎 Ark API) / local (本地 sentence-transformers)
    embedding_provider: str = Field(
        "ark",
    )
    embedding_model: str = Field(
        "doubao-embedding-vision-250615",
    )

    # 火山引擎 Ark API 配置
    ark_api_key: str = Field(
        "",
    )
    ark_base_url: str = Field(
        "https://ark.cn-beijing.volces.com/api/v3",
    )

    # 分块配置（token 计数，见 services/rag/chunking.py）
    chunk_size: int = Field(
        512,
    )
    chunk_overlap: int = Field(
        64,
    )

    # 混合检索配置（dense ⊕ sparse，RRF 融合，见 services/rag/vector_store.py）
    search_min_score: float = Field(
        0.2,
    )
    search_rrf_k: int = Field(
        60,
    )
    search_chunks_per_doc: int = Field(
        2,
    )
    search_candidate_limit: int = Field(
        50,
    )
    # 混合检索两侧权重：dense 主导，sparse 温和补充，
    # 避免宽泛关键词（如 "Agent"）的噪声稀释语义排序
    search_dense_weight: float = Field(
        1.0,
    )
    search_sparse_weight: float = Field(
        0.3,
    )

    # 向量数据库配置（PostgreSQL + pgvector）
    # 各项留空时 fallback 到上面的主库配置（db_host 等），实现"一个数据库"部署
    vector_db_host: str = Field(
        "",
    )
    vector_db_port: int = Field(
        0,
    )
    vector_db_name: str = Field(
        "",
    )
    vector_db_user: str = Field(
        "",
    )
    vector_db_password: str = Field(
        "",
    )
    vector_db_table: str = Field(
        "document_vectors",
    )
    # 向量维度: 0 表示自动检测（首次嵌入时确定）
    vector_dimensions: int = Field(
        0,
    )

    model_config = {
        "env_prefix": "AKM_",
        "env_file": str(BASE_DIR / ".env"),
    }

    @property
    def db_url(self) -> str:
        """数据库连接 URL."""
        if self.db_type == "postgres":
            return (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        # SQLite
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_file}"

    @property
    def vector_db_conn(self) -> dict:
        """向量库连接参数（未配置时 fallback 到主库）."""
        return {
            "host": self.vector_db_host or self.db_host,
            "port": self.vector_db_port or self.db_port,
            "dbname": self.vector_db_name or self.db_name,
            "user": self.vector_db_user or self.db_user,
            "password": self.vector_db_password or self.db_password,
        }

    @property
    def knowledge_paths(self) -> list[Path]:
        """知识库目录列表."""
        if not self.knowledge_roots:
            default = Path.home() / "Knowledge"
            default.mkdir(parents=True, exist_ok=True)
            return [default]

        paths = []
        for root in self.knowledge_roots.split(","):
            root = root.strip()
            if root:
                path = Path(root).expanduser()
                if path.exists():
                    paths.append(path)
        return paths


settings = Settings()
