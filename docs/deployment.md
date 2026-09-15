# 部署指南

> 面向部署者:把 AKM 跑起来的两条路径 —— **Hub**(server+web 单容器,一台)与 **akm-node**(每台知识源机器一条命令安装)。
> 开发仓内源码运行方式见 [README.md](../README.md)「快速启动」。

## 总览

```
┌─────────────────────────────┐        ┌──────────────────────────┐
│  Hub 机器                    │        │  知识源机器(可多台)      │
│  ghcr.io/wangboy91/akm-hub  │ ◄────  │  akm-node(一键安装)      │
│  Web + REST/WS/MCP, :8000   │  WS/HTTP 同步、检索             │
└─────────────────────────────┘        └──────────────────────────┘
```

- **Hub**:单容器同时提供 Web 界面与 API,知识库目录只读挂载,数据(SQLite)持久化于卷。
- **akm-node**:轻量客户端,扫描本机 Markdown 目录同步到 Hub;本机智能体经 `akm-node --mcp` 获得检索工具。

---

## 1. 部署 Hub(容器)

### 1.1 前置

- Docker 与 Docker Compose v2
- 一个存放知识库 Markdown 的目录(只读挂载给 Hub;由节点同步的文档则来自各节点机器)

### 1.2 启动

从 [GitHub Releases](https://github.com/wangboy91/AgentKnowledgeMesh/releases) 下载 `docker-compose.yml`(版本已固化),同目录可选创建 `.env`:

```bash
# .env 示例
KNOWLEDGE_DIR=/srv/knowledge      # 本机知识库目录(挂载为只读)
AKM_ADMIN_USERNAME=admin
AKM_ADMIN_PASSWORD=改成强密码      # 不设则首启生成随机密码,见 1.3
```

```bash
docker compose up -d
```

浏览器打开 `http://<服务器IP>:8000` 即为 Web 界面(与 API 同端口)。

固定版本部署:compose 中镜像 tag 即发布版本(如 `ghcr.io/wangboy91/akm-hub:v0.2.0`),回滚改回旧 tag 重启即可;也可用环境变量 `AKM_HUB_VERSION=v0.2.0` 指定。

### 1.3 管理员初始化

- 配置了 `AKM_ADMIN_PASSWORD` → 首次启动(空数据库)直接用该账号登录;
- 未配置 → 首次启动生成随机一次性密码,打印在容器日志:

```bash
docker compose logs akm-hub | grep 一次性密码
```

登录后建议立即在 Web「设置」页修改密码。忘记密码时,在 Hub 所在机器进入容器执行 `uv run akm-hub reset-password admin`(需源码方式,容器内可 `docker compose exec akm-hub uv run akm-hub reset-password admin`)。

### 1.4 数据持久化

| 内容 | 位置 |
| --- | --- |
| SQLite 数据库 | 卷 `akm-hub-data`(`AKM_DB_PATH=/app/data/agentvault.db`) |
| 知识库目录 | 宿主机 `KNOWLEDGE_DIR` 只读挂载 `/knowledge` |

备份即备份该卷;PostgreSQL 模式参见仓库 `src/docker-compose.pg.yml`(自行构建镜像或参照改造)。

### 1.5 GHCR 镜像可见性

首次由 Actions 推送的包在 GHCR 可能默认为 private:到 GitHub → Packages → `akm-hub` → Package settings → Change visibility → Public,否则其他机器 `docker pull` 需要登录。

---

## 2. 安装 akm-node(每台知识源机器)

### 2.1 一键安装

macOS / Linux:

```bash
curl -fsSL https://github.com/wangboy91/AgentKnowledgeMesh/releases/latest/download/install-akm-node.sh | bash
```

Windows(PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/wangboy91/AgentKnowledgeMesh/releases/latest/download/install-akm-node.ps1 | iex"
```

脚本自动完成:检测/安装 uv → 从 Release 下载 `akm_shared`/`akm_node` wheel → `uv tool install` 出全局 `akm-node` 命令。

- 锁定版本:`AKM_VERSION=0.2.0` 环境变量后再执行;
- 升级:重新执行安装脚本(等价于升级到目标版本,凭证保留);
- 回滚:`AKM_VERSION=<旧版>` 再执行一次。

### 2.2 接入 Hub

```bash
akm-node login
```

交互输入:Hub API 地址(如 `http://<服务器IP>:8000/api`)、管理员用户名/密码。成功后凭证写入 `~/.akm-node/.env`(路径可用 `AKM_NODE_ENV_FILE` 覆盖),之后常驻运行无需交互:

```bash
akm-node          # 前台常驻;或用 systemd / 任务计划程序 / pm2 托管
```

节点默认扫描 `~/Knowledge`(存在时);配置目录:

```bash
# ~/.akm-node/.env
AKM_KNOWLEDGE_ROOTS=/path/to/notes,/path/to/docs   # 逗号分隔多个
```

同步为 hash-first 增量:首轮全量上传,之后只传变更;快照存于 `~/.akm-node/sync_state.json`。

### 2.3 验证

- Web 端「节点」页可见该节点,知识库页出现该机器的文档;
- `akm-node --mcp`(下节)能检索到内容。

---

## 3. 本机智能体接入检索(MCP)

装有 akm-node 的机器上,智能体(Claude Code / Codex 等)直接用节点做 MCP 入口,免配 Hub 地址与凭证:

```json
{
  "mcpServers": {
    "agentknowledge": {
      "command": "akm-node",
      "args": ["--mcp"]
    }
  }
}
```

工具集与 Hub MCP 完全一致:

| 工具 | 说明 |
| --- | --- |
| `search_documents` | 关键词检索;`mode=semantic` 走 Hub 语义混合检索 |
| `get_document` | 取文档全文 |
| `list_documents` | 列文档(可按节点过滤) |

Claude Code 一条命令接入:

```bash
claude mcp add agentknowledge -- akm-node --mcp
```

远程/无节点机器的替代形态(Hub SSE / Hub stdio)见 [README.md](../README.md)「AI 工具接入(MCP)」。

---

## 4. 常见问题

| 问题 | 处理 |
| --- | --- |
| `docker pull ghcr.io/...` 401/无权限 | GHCR 包还是 private,见 §1.5 |
| PowerShell 远程脚本被策略拦截 | 下载脚本后 `powershell -ExecutionPolicy Bypass -File install-akm-node.ps1` |
| 安装后新终端才有 `akm-node` | PATH 刷新所致,重开终端即可 |
| 节点凭证失效(Web 端重置过 token) | 重新 `akm-node login` |
| 想换知识库目录 | 改 `~/.akm-node/.env` 的 `AKM_KNOWLEDGE_ROOTS` 后重启节点 |
| Hub 换了地址 | 重新 `akm-node login` 输入新地址(凭证会刷新) |

---

## 5. 发版(维护者)

1. 合入代码后,由维护者执行:`git tag v0.2.0 && git push origin v0.2.0`
2. GitHub Actions(`.github/workflows/release.yml`)自动:构建 wheels → 推镜像到 GHCR → 创建 Release(附 wheels、安装脚本、版本固化 compose)
3. 本地构建产物验证:`powershell -ExecutionPolicy Bypass -File deploy/build-release.ps1`(产出 `src/dist/*.whl`,可配合 `AKM_WHEEL_DIR` 干跑安装脚本)
