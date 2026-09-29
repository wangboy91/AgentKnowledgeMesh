"""`akm-node login` 的 Hub 地址推导(subpath-deployment)。

Hub 部署在反向代理子路径下时(如 `https://xx.com/akm/`),用户填的 API 地址是
`https://xx.com/akm/api`;推导出的 WS 地址必须保留该前缀,否则节点会连到域名根
的 `/ws` 而 404。节点侧无其它代码改动 —— `hub_api_url` / `hub_url` 都是显式
完整地址,前缀天然被保留。
"""

import pytest

from app.login import _derive_ws_url


@pytest.mark.parametrize(
    ("hub_api_url", "expected"),
    [
        # 根路径部署
        ("http://localhost:8000/api", "ws://localhost:8000/ws"),
        ("http://localhost:8000/api/", "ws://localhost:8000/ws"),
        # 单层前缀
        ("http://localhost:8000/akm/api", "ws://localhost:8000/akm/ws"),
        ("https://xx.com/akm/api", "wss://xx.com/akm/ws"),
        # 多层前缀
        ("https://xx.com/a/b/c/api", "wss://xx.com/a/b/c/ws"),
        # 带尾斜杠 / 空格
        ("https://xx.com/akm/api/", "wss://xx.com/akm/ws"),
        ("  https://xx.com/akm/api  ", "wss://xx.com/akm/ws"),
        # 前缀本身就叫 api 的极端情形:只剥末尾那一段
        ("https://xx.com/api/api", "wss://xx.com/api/ws"),
    ],
)
def test_derive_ws_url_keeps_deploy_prefix(hub_api_url, expected):
    assert _derive_ws_url(hub_api_url) == expected
