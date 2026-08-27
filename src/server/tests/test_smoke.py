"""冒烟测试：验证应用包可导入、可创建."""

from fastapi.testclient import TestClient

from app.config import BASE_DIR, settings
from app.main import app

client = TestClient(app)


def test_config_paths_anchored():
    """配置路径应锚定到项目目录，与 CWD 无关."""
    assert BASE_DIR.name == "server"
    assert settings.db_path.endswith("agentvault.db")
    assert str(BASE_DIR) in settings.db_path


def test_health_endpoint():
    """健康检查应正常响应."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_core_api_routes():
    """核心 API 路由应可访问."""
    # rag/stats 不依赖数据库内容
    resp = client.get("/api/rag/stats")
    assert resp.status_code == 200
    assert "total_chunks" in resp.json()

    # search 缺少参数应返回 422（证明路由存在而非 404）
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_rag_provider_configured():
    """RAG 供应商配置应有效."""
    from app.services.rag.embeddings import _PROVIDERS

    assert settings.embedding_provider in _PROVIDERS
