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
    """核心 API 路由应受鉴权保护(account-auth)."""
    # 未携带凭证访问受保护端点一律 401(依赖在参数校验前拦截)
    resp = client.get("/api/rag/stats")
    assert resp.status_code == 401

    resp = client.get("/api/search")
    assert resp.status_code == 401

    # 健康检查保持公开
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_rag_provider_configured():
    """RAG 供应商配置应有效."""
    from app.services.rag.embeddings import _PROVIDERS

    assert settings.embedding_provider in _PROVIDERS


def test_env_prefix(monkeypatch):
    """环境变量前缀 AKM_ 生效，AV_ 前缀不再兼容."""
    from app.config import Settings

    monkeypatch.delenv("AKM_PORT", raising=False)
    monkeypatch.delenv("AV_PORT", raising=False)

    # AKM_ 前缀生效
    monkeypatch.setenv("AKM_PORT", "9002")
    assert Settings(_env_file=None).port == 9002

    # AV_ 前缀不再被识别，回退到默认值 8000
    monkeypatch.delenv("AKM_PORT", raising=False)
    monkeypatch.setenv("AV_PORT", "9001")
    assert Settings(_env_file=None).port == 8000
