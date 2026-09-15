"""配置解析单测(app/config.py):env 文件位置与优先级.

覆盖三情形(spec:凭证与配置持久化):
- 仓库 .env 存在且用户 .env 不存在 → 仓库文件生效(开发场景兼容)
- 两者并存 → 用户目录文件覆盖仓库文件
- AKM_NODE_ENV_FILE 自定义路径 → USER_ENV_FILE 指向该路径
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
    "AKM_KNOWLEDGE_ROOTS",
    "AKM_NODE_ENV_FILE",
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
