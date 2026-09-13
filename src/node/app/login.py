"""akm-node login:节点接入登录(account-auth 能力).

交互输入 Hub API 地址与管理员账号密码,经
POST /api/auth/login -> POST /api/nodes/register 换取节点 token,
并写入本地 .env(已 gitignore),此后 `uv run akm-node` 无头常驻。
"""

import asyncio
import getpass
import sys
from pathlib import Path

import httpx

from app.config import BASE_DIR, settings


def _read_password(prompt: str) -> str:
    """读密码:交互终端用 getpass 隐藏输入;管道/重定向时回退普通读取.

    Windows 下 getpass 直读控制台,stdin 被重定向(脚本/CI)时会永久阻塞,
    因此非 tty 环境必须走普通读取。
    """
    if sys.stdin.isatty() and sys.stderr.isatty():
        return getpass.getpass(prompt)
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip("\r\n")


def _derive_ws_url(hub_api_url: str) -> str:
    """由 API 地址(http(s)://host:port/api)推导 WS 地址(ws(s)://host:port/ws)."""
    base = hub_api_url.strip().rstrip("/")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    scheme = "wss://" if base.startswith("https://") else "ws://"
    host = base.split("://", 1)[-1]
    return scheme + host + "/ws"


def _update_env(path: Path, updates: dict) -> None:
    """更新 .env 中的键,保留其余行(键不存在则追加)."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    result, seen = [], set()
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                result.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        result.append(line)
    for key, value in updates.items():
        if key not in seen:
            result.append(f"{key}={value}")
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


async def _exchange_credentials(hub_api_url: str, username: str, password: str, node_name: str) -> dict:
    """登录并注册节点,返回 {node_id, node_token}.

    已有节点身份(AKM_NODE_ID)时携带它,Hub 复用同一节点记录并轮换 token,
    避免每次重登都新建节点。
    """
    base = hub_api_url.rstrip("/")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base}/auth/login", json={"username": username, "password": password}
        )
        if resp.status_code != 200:
            raise RuntimeError(f"登录失败({resp.status_code}):用户名或密码错误")
        access_token = resp.json()["access_token"]

        payload = {"node_name": node_name, "platform": settings.get_platform()}
        if settings.node_id:
            payload["node_id"] = settings.node_id
        resp = await client.post(
            f"{base}/nodes/register",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"节点注册失败({resp.status_code}):{resp.text}")
        data = resp.json()
        return {"node_id": data["node_id"], "node_token": data["node_token"]}


def _run_exchange(coro):
    """在可用的事件循环中执行协程.

    CLI 入口(无循环)直接 asyncio.run;节点运行中重登时已处于事件循环内,
    asyncio.run 不允许嵌套,故放到独立线程的新循环中执行(主循环不受影响)。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def prompt_and_exchange(default_hub_api_url: str) -> tuple[dict, str]:
    """交互收集凭证 → 换取节点 token → 写入 .env.

    供 CLI 登录入口与运行中节点的现场重登共用。
    返回 (凭证 {node_id, node_token}, hub_api_url)。
    """
    print("=" * 50)
    print("🔐 AgentKnowledgeMesh 节点登录")
    print("=" * 50)

    hub_api_url = input(f"Hub API 地址 [{default_hub_api_url}]: ").strip() or default_hub_api_url
    username = input("管理员用户名: ").strip()
    if not username:
        raise RuntimeError("用户名不能为空")
    password = _read_password("密码: ")
    if not password:
        raise RuntimeError("密码不能为空")

    node_name = settings.get_node_name()
    result = _run_exchange(_exchange_credentials(hub_api_url, username, password, node_name))

    _update_env(
        BASE_DIR / ".env",
        {
            "AKM_HUB_API_URL": hub_api_url,
            "AKM_HUB_URL": _derive_ws_url(hub_api_url),
            "AKM_NODE_ID": result["node_id"],
            "AKM_NODE_TOKEN": result["node_token"],
        },
    )
    return result, hub_api_url


def run_login() -> int:
    """交互式登录入口,返回进程退出码."""
    try:
        result, _ = prompt_and_exchange(settings.hub_api_url)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:  # 网络错误等
        print(f"❌ 无法连接 Hub:{e}")
        return 1

    print("=" * 50)
    print(f"✅ 接入成功:node_id={result['node_id']}")
    print(f"   凭证已写入 {BASE_DIR / '.env'}")
    print("   之后直接运行 `uv run akm-node` 即可无头常驻")
    print("=" * 50)
    return 0
