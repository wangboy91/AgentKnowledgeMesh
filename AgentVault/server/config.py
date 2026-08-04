"""AgentVault 配置管理."""

from pathlib import Path
from pydantic_settings import BaseSettings

# 项目根目录（server 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """应用配置，支持环境变量覆盖."""

    # 服务配置
    app_name: str = "AgentVault"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # 数据库配置
    # 类型: sqlite / postgres
    db_type: str = "sqlite"

    # SQLite 配置
    db_path: str = "data/agentvault.db"

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

    model_config = {
        "env_prefix": "AV_",
        "env_file": str(PROJECT_ROOT / ".env"),
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
