"""CLI 入口与登录衔接单测(app/__main__.py / app/login.py / app/runner.py).

覆盖 login-auto-run 变更:
- --help / -h 列出全部命令,说明断开(Ctrl+C)与断线重连(5 秒),
  且短路优先(携带其他参数时同样只输出帮助,不触发登录/连接)
- run_login 成功/失败返回值与"自动接入"提示
- 登录写入新凭证后,HubClient 以新 NodeSettings 构造(防模块级单例持旧值)
"""

import app.login
import app.runner
import pytest
from app import __main__ as cli
from app.config import NodeSettings
from app.runner import HubClient


def test_help_lists_commands_and_run_control(capsys, monkeypatch):
    """--help 列出命令用法与断开/重连说明."""
    monkeypatch.setattr("sys.argv", ["akm-node", "--help"])
    cli.main()
    out = capsys.readouterr().out
    for expected in ("login", "--mcp", "--version", "Ctrl+C", "5 秒"):
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
