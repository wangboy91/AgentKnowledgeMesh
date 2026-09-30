"""CLI 入口与登录衔接单测(app/__main__.py / app/login.py / app/runner.py).

覆盖 login-auto-run 变更:
- --help / -h 列出全部命令,说明断开(Ctrl+C)与断线重连(5 秒),
  且短路优先(携带其他参数时同样只输出帮助,不触发登录/连接)
- run_login 成功/失败返回值与"自动接入"提示
- 登录写入新凭证后,HubClient 以新 NodeSettings 构造(防模块级单例持旧值)

覆盖 node-env-login 变更:
- 无凭证但配置了 AKM_HUB_USERNAME / AKM_HUB_PASSWORD → 启动自动登录并进入运行循环
- 已有凭证 → 不调用登录/注册(不轮换 token)
- 自动登录失败 / 无凭证且未配置账号 → 退出码 1,不启动客户端
- 配置了账号也不静默重登(不解除 Hub 端禁用)
"""

import app.login
import app.runner
import pytest
from app import __main__ as cli
from app.config import NodeSettings
from app.runner import HubClient

# 清掉可能来自真实 .env / 进程环境的账号变量,避免测试间串味
_ACCOUNT_KEYS = ("AKM_NODE_TOKEN", "AKM_HUB_USERNAME", "AKM_HUB_PASSWORD")


def _clean_env(monkeypatch) -> None:
    for key in _ACCOUNT_KEYS:
        monkeypatch.delenv(key, raising=False)


def _isolated_settings(monkeypatch) -> NodeSettings:
    """构造不读任何 .env 文件的配置,并替换 CLI 模块级单例.

    开发机上 src/node/.env 与 ~/.akm-node/.env 可能带真实凭证,直接断言单例
    会随机器而异;替换为 _env_file=None 的实例后,只有进程环境变量生效。
    """
    fresh = NodeSettings(_env_file=None)
    monkeypatch.setattr(cli, "settings", fresh)
    return fresh


def test_help_lists_commands_and_run_control(capsys, monkeypatch):
    """--help 列出命令用法与断开/重连说明."""
    monkeypatch.setattr("sys.argv", ["akm-node", "--help"])
    cli.main()
    out = capsys.readouterr().out
    for expected in ("login", "--mcp", "--version", "Ctrl+C", "5 秒", "AKM_HUB_USERNAME"):
        assert expected in out, f"帮助输出缺少关键内容: {expected}"


def test_help_short_flag_and_priority(capsys, monkeypatch):
    """-h 等价;与其他参数并存时仍只输出帮助,不触发登录或客户端."""
    monkeypatch.setattr("sys.argv", ["akm-node", "-h", "login"])
    started = []
    monkeypatch.setattr(cli, "HubClient", lambda *a, **k: started.append(1))
    monkeypatch.setattr(
        app.login, "run_login", lambda: started.append("login") or 1
    )
    cli.main()
    out = capsys.readouterr().out
    assert "用法" in out
    assert not started, "帮助短路失效:触发了登录或客户端启动"


def test_run_login_success_returns_zero_with_auto_run_hint(monkeypatch, capsys):
    """登录成功返回 0,提示即将自动接入并同步."""
    monkeypatch.setattr(
        app.login,
        "prompt_and_exchange",
        lambda *a, **k: ({"node_id": "nid", "node_token": "tok"}, "http://x/api"),
    )
    assert app.login.run_login() == 0
    out = capsys.readouterr().out
    assert "自动" in out


def test_run_login_failure_returns_nonzero(monkeypatch, capsys):
    """登录失败返回 1,不进入运行循环."""
    def _boom(*a, **k):
        raise RuntimeError("登录失败(401):用户名或密码错误")

    monkeypatch.setattr(app.login, "prompt_and_exchange", _boom)
    assert app.login.run_login() == 1


def test_hubclient_uses_fresh_settings(monkeypatch):
    """登录写入新凭证后,以新 NodeSettings 构造的 HubClient 读到新值.

    用进程环境变量模拟登录后写入的新凭证(优先级高于任何 .env 文件),
    防止模块级 settings 单例持旧值的回归。
    """
    monkeypatch.setenv("AKM_NODE_TOKEN", "brand-new-token")
    monkeypatch.setenv("AKM_HUB_URL", "ws://fresh-hub:8000/ws")
    monkeypatch.setenv("AKM_HUB_API_URL", "http://fresh-hub:8000/api")

    fresh = NodeSettings()
    client = HubClient(fresh)

    assert client.transport.token == "brand-new-token"
    assert client.transport.settings.hub_url == "ws://fresh-hub:8000/ws"
    assert client.sync.settings is fresh


def test_hubclient_defaults_to_module_settings():
    """无参构造仍使用模块级单例(默认运行入口行为不变)."""
    client = HubClient()
    assert client.transport.settings is app.runner.default_settings


def test_login_success_enters_run_loop_with_fresh_credentials(monkeypatch, capsys):
    """login 成功后进程不退出:以新凭证构造客户端并进入运行循环.

    覆盖 login-auto-run 的核心衔接(入口分支 → 新 NodeSettings → HubClient.run),
    防止"登录写凭证后直接退出"的回归。
    """
    monkeypatch.setattr("sys.argv", ["akm-node", "login"])
    monkeypatch.setattr(app.login, "run_login", lambda: 0)
    # 模拟 login 刚写入 .env 的新凭证(进程环境变量优先级最高)
    monkeypatch.setenv("AKM_NODE_TOKEN", "token-written-by-login")
    monkeypatch.setenv("AKM_HUB_URL", "ws://hub-after-login:8000/ws")

    seen = {}

    class _FakeClient:
        def __init__(self, settings=None):
            seen["settings"] = settings

        async def run(self):
            seen["ran"] = True

    monkeypatch.setattr(cli, "HubClient", _FakeClient)

    cli.main()

    assert seen.get("ran") is True, "login 成功后未进入运行循环"
    assert seen["settings"] is not app.runner.default_settings
    assert seen["settings"].node_token == "token-written-by-login"
    assert seen["settings"].hub_url == "ws://hub-after-login:8000/ws"


def test_login_failure_exits_nonzero_without_run(monkeypatch):
    """登录失败以退出码 1 结束,不进入运行循环."""
    monkeypatch.setattr("sys.argv", ["akm-node", "login"])
    monkeypatch.setattr(app.login, "run_login", lambda: 1)
    started = []
    monkeypatch.setattr(cli, "HubClient", lambda *a, **k: started.append(1))

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    assert not started, "登录失败仍启动了客户端"


def test_try_relogin_rebuilds_components_with_new_credentials(monkeypatch):
    """凭证失效现场重登:重登成功后以新凭证重建 transport / sync(回归保障).

    `HubClient.__init__` 改为可选注入配置后,重登路径必须仍走
    "重读 .env → 新建 NodeSettings → 重建组件",不能复用旧凭证的组件。
    """
    monkeypatch.setenv("AKM_NODE_TOKEN", "expired-token")
    monkeypatch.setenv("AKM_HUB_URL", "ws://old-hub:8000/ws")
    # 用实例构造(与运行入口一致):模块级单例在 import 时就已固化旧凭证
    client = HubClient(NodeSettings())
    old_transport, old_sync = client.transport, client.sync
    assert old_transport.token == "expired-token"

    class _Tty:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", _Tty())
    monkeypatch.setattr("sys.stderr", _Tty())
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    def _fake_prompt_and_exchange(default_hub_api_url):
        # 模拟交互重登后写入的新凭证
        monkeypatch.setenv("AKM_NODE_TOKEN", "rotated-token")
        monkeypatch.setenv("AKM_HUB_URL", "ws://new-hub:8000/ws")
        return {"node_id": "nid", "node_token": "rotated-token"}, "http://new-hub:8000/api"

    monkeypatch.setattr(app.login, "prompt_and_exchange", _fake_prompt_and_exchange)

    assert client._try_relogin() is True
    assert client.transport is not old_transport
    assert client.sync is not old_sync
    assert client.transport.token == "rotated-token"
    assert client.transport.settings.hub_url == "ws://new-hub:8000/ws"
    assert client.sync.settings is client.transport.settings


def test_try_relogin_skipped_in_non_interactive_env(monkeypatch):
    """非交互环境(脚本/服务)不触发重登,保持重试循环."""
    client = HubClient(NodeSettings())

    class _NotTty:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr("sys.stdin", _NotTty())
    monkeypatch.setattr("sys.stderr", _NotTty())
    called = []
    monkeypatch.setattr(app.login, "prompt_and_exchange", lambda *a, **k: called.append(1))

    assert client._try_relogin() is False
    assert not called, "非交互环境仍尝试了交互重登"


def test_try_relogin_ignores_env_account(monkeypatch):
    """配置了 Hub 账号也不静默重登(node-env-login 刻意留出的边界).

    Hub 的 register 会清除 disabled,静默重登会让 admin 的"禁用"被无人值守
    进程自动解除;故凭证失效后仍走既有语义:非交互保持重试。
    """
    _clean_env(monkeypatch)
    monkeypatch.setenv("AKM_HUB_USERNAME", "admin")
    monkeypatch.setenv("AKM_HUB_PASSWORD", "pw")
    client = HubClient(NodeSettings(_env_file=None))

    class _NotTty:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr("sys.stdin", _NotTty())
    monkeypatch.setattr("sys.stderr", _NotTty())
    called = []
    monkeypatch.setattr(app.login, "prompt_and_exchange", lambda *a, **k: called.append("prompt"))
    monkeypatch.setattr(app.login, "auto_login", lambda *a, **k: called.append("auto"))

    assert client._try_relogin() is False
    assert not called, "配置了账号仍触发了重登"


# ---- node-env-login:环境变量账号与启动自动登录 ----


def _fake_client_recorder(monkeypatch) -> dict:
    """把 cli.HubClient 换成记录用假客户端,返回记录容器."""
    seen: dict = {}

    class _FakeClient:
        def __init__(self, settings=None):
            seen["settings"] = settings

        async def run(self):
            seen["ran"] = True

    monkeypatch.setattr(cli, "HubClient", _FakeClient)
    return seen


def test_env_account_auto_login_then_run(monkeypatch, capsys):
    """无凭证 + 配置账号 → 自动登录换取凭证并进入运行循环."""
    _clean_env(monkeypatch)
    monkeypatch.setattr("sys.argv", ["akm-node"])
    monkeypatch.setenv("AKM_HUB_USERNAME", "admin")
    monkeypatch.setenv("AKM_HUB_PASSWORD", "pw")
    module_settings = _isolated_settings(monkeypatch)

    calls = []

    def _fake_auto_login(config):
        calls.append(config)
        return config.model_copy(update={"node_id": "nid-auto", "node_token": "auto-token"})

    monkeypatch.setattr(app.login, "auto_login", _fake_auto_login)
    seen = _fake_client_recorder(monkeypatch)

    cli.main()

    assert len(calls) == 1, "未触发自动登录"
    assert seen.get("ran") is True, "自动登录后未进入运行循环"
    assert seen["settings"].node_token == "auto-token"
    assert seen["settings"].node_id == "nid-auto"
    # --mcp 等模块读模块级单例,凭证必须同步过去
    assert module_settings.node_token == "auto-token"


def test_existing_token_skips_auto_login(monkeypatch):
    """已有凭证时直接用 token,不调用登录/注册(不轮换 token)."""
    _clean_env(monkeypatch)
    monkeypatch.setattr("sys.argv", ["akm-node"])
    monkeypatch.setenv("AKM_HUB_USERNAME", "admin")
    monkeypatch.setenv("AKM_HUB_PASSWORD", "pw")
    monkeypatch.setenv("AKM_NODE_TOKEN", "existing-token")
    _isolated_settings(monkeypatch)

    called = []
    monkeypatch.setattr(app.login, "auto_login", lambda *a, **k: called.append(1))
    seen = _fake_client_recorder(monkeypatch)

    cli.main()

    assert not called, "已有凭证仍触发了登录"
    assert seen["settings"].node_token == "existing-token"


def test_no_token_and_no_account_exits_with_hint(monkeypatch, capsys):
    """无凭证且未配置账号 → 提示引导 + 退出码 1,不启动客户端."""
    _clean_env(monkeypatch)
    monkeypatch.setattr("sys.argv", ["akm-node"])
    _isolated_settings(monkeypatch)

    started = []
    monkeypatch.setattr(cli, "HubClient", lambda *a, **k: started.append(1))

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "akm-node login" in out
    assert "AKM_HUB_USERNAME" in out
    assert not started, "无凭证时仍启动了客户端"


def test_auto_login_failure_exits_nonzero(monkeypatch, capsys):
    """自动登录失败(账号密码错误/网络不通)→ 退出码 1,不进入运行循环."""
    _clean_env(monkeypatch)
    monkeypatch.setattr("sys.argv", ["akm-node"])
    monkeypatch.setenv("AKM_HUB_USERNAME", "admin")
    monkeypatch.setenv("AKM_HUB_PASSWORD", "wrong")
    _isolated_settings(monkeypatch)

    def _boom(config):
        raise RuntimeError("登录失败(401):用户名或密码错误")

    monkeypatch.setattr(app.login, "auto_login", _boom)
    started = []
    monkeypatch.setattr(cli, "HubClient", lambda *a, **k: started.append(1))

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    assert "自动登录失败" in capsys.readouterr().out
    assert not started


def test_auto_login_swaps_credentials_and_persists(monkeypatch, tmp_path, capsys):
    """auto_login:换取凭证 → 写回 .env → 返回注入凭证的新配置(原配置不动)."""
    _clean_env(monkeypatch)
    env_file = tmp_path / ".env"
    monkeypatch.setattr(app.login, "USER_ENV_FILE", env_file)

    config = NodeSettings(
        _env_file=None,
        hub_api_url="http://hub:8000/api",
        hub_username="admin",
        hub_password="pw",
    )
    seen = {}

    async def _fake_exchange(hub_api_url, username, password, node_name, cfg=None):
        seen.update(
            hub_api_url=hub_api_url, username=username, password=password, config=cfg
        )
        return {"node_id": "nid-1", "node_token": "tok-1"}

    monkeypatch.setattr(app.login, "_exchange_credentials", _fake_exchange)

    fresh = app.login.auto_login(config)

    assert seen["hub_api_url"] == "http://hub:8000/api"
    assert seen["username"] == "admin"
    assert seen["config"] is config, "换取时未用传入配置(platform/node_id 会取到旧值)"
    assert fresh.node_token == "tok-1"
    assert fresh.node_id == "nid-1"
    assert config.node_token == "", "原配置被就地修改"

    persisted = env_file.read_text(encoding="utf-8")
    assert "AKM_NODE_TOKEN=tok-1" in persisted
    assert "AKM_NODE_ID=nid-1" in persisted
    assert "自动登录" in capsys.readouterr().out


def test_auto_login_requires_account(monkeypatch):
    """未配置账号时直接报错,不发网络请求."""
    _clean_env(monkeypatch)
    with pytest.raises(RuntimeError):
        app.login.auto_login(NodeSettings(_env_file=None))


def test_auto_login_tolerates_env_write_failure(monkeypatch, tmp_path, capsys):
    """凭证落盘失败(只读挂载/权限)只告警,仍返回可用配置."""
    _clean_env(monkeypatch)
    monkeypatch.setattr(app.login, "USER_ENV_FILE", tmp_path / "ro" / ".env")

    def _boom(path, updates):
        raise OSError("read-only file system")

    monkeypatch.setattr(app.login, "_update_env", _boom)

    async def _fake_exchange(hub_api_url, username, password, node_name, cfg=None):
        return {"node_id": "nid-2", "node_token": "tok-2"}

    monkeypatch.setattr(app.login, "_exchange_credentials", _fake_exchange)

    config = NodeSettings(_env_file=None, hub_username="admin", hub_password="pw")
    fresh = app.login.auto_login(config)

    assert fresh.node_token == "tok-2"
    assert "⚠️" in capsys.readouterr().out
