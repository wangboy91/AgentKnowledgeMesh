"""AgentKnowledgeMesh 配置管理."""

from pathlib import Path
from pydantic_settings import BaseSettings

# 项目根目录（src/server，即 app 包的父目录）
# 所有相对路径均锚定到此目录，与运行时 CWD 无关
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """应用配置，支持环境变量覆盖."""

    # 服务配置
    app_name: str = "AgentKnowledgeMesh"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # 数据库配置
    # 类型: sqlite / postgres
    db_type: str = "sqlite"

    # SQLite 配置（锚定到项目根目录，Docker 中通过 AV_DB_PATH 覆盖）
    db_path: str = str(BASE_DIR / "data" / "agentvault.db")

    # PostgreSQL 配置
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "agentvault"
    db_user: str = "postgres"
    db_password: str = ""

    # 知识库根目录，支持多个目录用逗号分隔
    # 例如: "/Users/me/obsidian-doc,/Users/me/projects/docs"
    knowledge_roots: str = ""

    # 扫描配置
    scan_extensions: list[str] = [".md"]
    max_file_size_mb: int = 10

    # 向量嵌入配置（支持多供应商切换）
    # 供应商: ark (火山引擎 Ark API) / local (本地 sentence-transformers)
    embedding_provider: str = "ark"
    embedding_model: str = "doubao-embedding-vision-250615"

    # 火山引擎 Ark API 配置
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # 分块配置
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 向量数据库配置（PostgreSQL + pgvector）
    # 各项留空时 fallback 到上面的主库配置（db_host 等），实现"一个数据库"部署
    vector_db_host: str = ""
    vector_db_port: int = 0
    vector_db_name: str = ""
    vector_db_user: str = ""
    vector_db_password: str = ""
    vector_db_table: str = "document_vectors"
    # 向量维度: 0 表示自动检测（首次嵌入时确定）
    vector_dimensions: int = 0

    model_config = {
        "env_prefix": "AV_",
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
