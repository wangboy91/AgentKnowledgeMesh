"""配置解析单测(app/config.py):env 文件位置与优先级.

覆盖三情形(spec:凭证与配置持久化):
- 仓库 .env 存在且用户 .env 不存在 → 仓库文件生效(开发场景兼容)
- 两者并存 → 用户目录文件覆盖仓库文件
- AKM_NODE_ENV_FILE 自定义路径 → USER_ENV_FILE 指向该路径
- 文件监听与对账配置(add-node-file-watch)
- Hub 账号配置与 has_hub_credentials 判定(node-env-login)
"""

import importlib
from pathlib import Path

from app import config
from app.config import NodeSettings

# 隔离:清掉可能存在的进程级 AKM_ 环境变量,避免干扰文件解析断言
_AKM_ENV_KEYS = [
    "AKM_NODE_TOKEN",
    "AKM_NODE_ID",
    "AKM_NODE_NAME",
    "AKM_HUB_URL",
    "AKM_HUB_API_URL",
    "AKM_HUB_USERNAME",
    "AKM_HUB_PASSWORD",
    "AKM_KNOWLEDGE_ROOTS",
    "AKM_NODE_ENV_FILE",
    "AKM_WATCH_ENABLED",
    "AKM_WATCH_DEBOUNCE_SECONDS",
    "AKM_WATCH_RECONCILE_SECONDS",
    "AKM_WATCH_EXCLUDE",
    "AKM_UPLOAD_BATCH_BYTES",
    "AKM_UPLOAD_BATCH_DOCS",
]


def _make_settings(monkeypatch, files: list[Path]) -> NodeSettings:
    """以指定 env 文件列表实例化 NodeSettings(模拟 model_config 的解析顺序)."""
    for key in _AKM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    # 按优先级从低到高传入(pydantic-settings 列表后者优先)
    return NodeSettings(_env_file=[str(f) for f in files])


def test_repo_env_applies_when_user_env_absent(tmp_path, monkeypatch):
    """仅仓库 .env 存在时其中的凭证生效."""
    repo_env = tmp_path / "repo.env"
    repo_env.write_text("AKM_NODE_TOKEN=repo-token\n", encoding="utf-8")
    user_env = tmp_path / "user.env"  # 不创建

    settings = _make_settings(monkeypatch, [repo_env, user_env])

    assert settings.node_token == "repo-token"


def test_user_env_overrides_repo_env(tmp_path, monkeypatch):
    """两者并存时用户目录文件优先."""
    repo_env = tmp_path / "repo.env"
    repo_env.write_text("AKM_NODE_TOKEN=repo-token\n", encoding="utf-8")
    user_env = tmp_path / "user.env"
    user_env.write_text("AKM_NODE_TOKEN=user-token\n", encoding="utf-8")

    settings = _make_settings(monkeypatch, [repo_env, user_env])

    assert settings.node_token == "user-token"


def test_custom_env_file_via_env_var(tmp_path, monkeypatch):
    """AKM_NODE_ENV_FILE 覆盖默认用户文件路径."""
    custom = tmp_path / "custom.env"
    monkeypatch.setenv("AKM_NODE_ENV_FILE", str(custom))
    try:
        reloaded = importlib.reload(config)
        assert reloaded.USER_ENV_FILE == custom
    finally:
        # 还原模块状态,避免影响后续测试/已导入引用
        monkeypatch.delenv("AKM_NODE_ENV_FILE", raising=False)
        importlib.reload(config)


def test_default_user_env_file(monkeypatch):
    """未配置覆盖时默认为 ~/.akm-node/.env."""
    monkeypatch.delenv("AKM_NODE_ENV_FILE", raising=False)
    reloaded = importlib.reload(config)
    try:
        assert reloaded.USER_ENV_FILE == Path.home() / ".akm-node" / ".env"
    finally:
        importlib.reload(config)


# ---- 文件监听与定时对账配置（add-node-file-watch） ----

def test_watch_defaults(monkeypatch):
    """监听默认开启、防抖 3 秒、对账 300 秒、无追加排除."""
    for key in _AKM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = NodeSettings(_env_file=None)

    assert settings.watch_enabled is True
    assert settings.watch_debounce_seconds == 3.0
    assert settings.watch_reconcile_seconds == 300
    assert settings.watch_exclude == ""
    assert settings.watch_excluded_names == set()


def test_watch_env_overrides(monkeypatch):
    """环境变量可覆盖；对账置 0 表示关闭."""
    monkeypatch.setenv("AKM_WATCH_ENABLED", "false")
    monkeypatch.setenv("AKM_WATCH_DEBOUNCE_SECONDS", "1.5")
    monkeypatch.setenv("AKM_WATCH_RECONCILE_SECONDS", "0")
    monkeypatch.setenv("AKM_WATCH_EXCLUDE", "vendor,tmp")
    try:
        settings = NodeSettings(_env_file=None)
        assert settings.watch_enabled is False
        assert settings.watch_debounce_seconds == 1.5
        assert settings.watch_reconcile_seconds == 0
        assert settings.watch_excluded_names == {"vendor", "tmp"}
    finally:
        for key in _AKM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)


def test_watch_excluded_names_ignores_blanks(monkeypatch):
    monkeypatch.setenv("AKM_WATCH_EXCLUDE", " a , ,b ")
    try:
        assert NodeSettings(_env_file=None).watch_excluded_names == {"a", "b"}
    finally:
        monkeypatch.delenv("AKM_WATCH_EXCLUDE", raising=False)


# ---- Hub 账号配置（node-env-login） ----

def test_hub_credentials_absent_by_default(monkeypatch):
    """未配置账号时字段为空、has_hub_credentials 为 False."""
    for key in _AKM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = NodeSettings(_env_file=None)

    assert settings.hub_username == ""
    assert settings.hub_password == ""
    assert settings.has_hub_credentials is False


def test_hub_credentials_require_both(monkeypatch):
    """只填一个视为未配置齐全(避免拿半个凭证去撞 401)."""
    monkeypatch.delenv("AKM_HUB_PASSWORD", raising=False)
    monkeypatch.setenv("AKM_HUB_USERNAME", "admin")
    try:
        assert NodeSettings(_env_file=None).has_hub_credentials is False

        monkeypatch.setenv("AKM_HUB_PASSWORD", "secret")
        assert NodeSettings(_env_file=None).has_hub_credentials is True
    finally:
        monkeypatch.delenv("AKM_HUB_USERNAME", raising=False)
        monkeypatch.delenv("AKM_HUB_PASSWORD", raising=False)


def test_hub_credentials_from_env_file(tmp_path, monkeypatch):
    """账号也可写在 .env 文件里(与其余配置同一解析顺序)."""
    for key in _AKM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / "node.env"
    env_file.write_text(
        "AKM_HUB_USERNAME=admin\nAKM_HUB_PASSWORD=secret\n", encoding="utf-8"
    )

    settings = NodeSettings(_env_file=str(env_file))

    assert settings.has_hub_credentials is True
    assert settings.hub_username == "admin"


# ---- 上传分批配置（node-upload-batching） ----

def test_upload_batch_defaults(monkeypatch):
    """默认单请求 512 KiB / 50 条."""
    for key in _AKM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    settings = NodeSettings(_env_file=None)

    assert settings.upload_batch_bytes == 512 * 1024
    assert settings.upload_batch_docs == 50


def test_upload_batch_env_overrides(monkeypatch):
    """环境变量可覆盖两个上限."""
    monkeypatch.setenv("AKM_UPLOAD_BATCH_BYTES", "1048576")
    monkeypatch.setenv("AKM_UPLOAD_BATCH_DOCS", "10")
    try:
        settings = NodeSettings(_env_file=None)
        assert settings.upload_batch_bytes == 1048576
        assert settings.upload_batch_docs == 10
    finally:
        for key in _AKM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)


def test_upload_batch_non_positive_means_unlimited(monkeypatch):
    """<= 0 表示该维度不限(逃生舱:完全退回分批前行为)."""
    monkeypatch.setenv("AKM_UPLOAD_BATCH_BYTES", "0")
    monkeypatch.setenv("AKM_UPLOAD_BATCH_DOCS", "-1")
    try:
        settings = NodeSettings(_env_file=None)
        assert settings.upload_batch_bytes == 0
        assert settings.upload_batch_docs == -1
    finally:
        for key in _AKM_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
