"""快速查看数据库中已注册的 Node 与 API Token 数据,用于多节点接入/鉴权排查。

测试/验证内容:
- nodes 表:节点注册记录(id/名称/平台/IP/状态/禁用标记/token 前缀/心跳时间)
- api_tokens 表:API 令牌记录(名称/前缀/角色/撤销时间)

前置条件:
- 已配置 src/server/.env(AKM_DB_HOST/PORT/USER/PASSWORD/NAME)
- PostgreSQL 主库可达

运行方式:
- cd src/server && uv run python scripts/query_nodes.py
"""
import asyncio
from pathlib import Path

env = {}
for line in Path('.env').read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

import asyncpg


async def main():
    conn = await asyncpg.connect(
        host=env['AKM_DB_HOST'],
        port=int(env['AKM_DB_PORT']),
        user=env['AKM_DB_USER'],
        password=env['AKM_DB_PASSWORD'],
        database=env['AKM_DB_NAME'],
    )
    print('=== nodes ===')
    rows = await conn.fetch(
        'SELECT id, name, platform, ip, status, disabled, token, last_heartbeat, created_at, updated_at '
        'FROM nodes ORDER BY created_at'
    )
    print('node count:', len(rows))
    for r in rows:
        d = dict(r)
        tok = d.get('token') or ''
        d['token'] = tok[:8] + '...' if tok else None
        print(d)

    print()
    print('=== api_tokens ===')
    rows2 = await conn.fetch(
        'SELECT id, name, token_prefix, role, revoked_at FROM api_tokens ORDER BY id'
    )
    print('token count:', len(rows2))
    for r in rows2:
        print(dict(r))

    await conn.close()


asyncio.run(main())
