# AgentKnowledgeMesh

> Your distributed memory layer for AI Agents.
> 面向 AI Agent 时代的分布式知识库:把散落在各台电脑上的 Markdown 文档汇成一个可检索的知识网络,并经 MCP / Context API 供智能体直接取用。

## 功能

**已交付(V0.1 – V0.3)**

- 📁 本地 Markdown 递归扫描,hash 增量索引(SQLite / PostgreSQL)
- 🔍 关键词搜索 + 语义检索:混合检索(dense ⊕ sparse、RRF 融合、Markdown 感知分块)
- 🌐 Hub + Node 多节点:WebSocket 注册/心跳、文档同步、节点文档向量同步
- 🖥️ Web 界面:文档浏览/在线编辑、暗色亮色主题、可拖侧边栏
- 🤖 Context API + MCP Server(stdio / SSE),AI 工具直接接入
- 📄 文档转换:PDF / Word / HTML / URL → Markdown

**进行中(V0.4 · 账号与治理)**

- 🔐 账号体系(admin / viewer)+ 全端点鉴权
- ⌨️ 节点 CLI 登录接入(`akm-node login`),token 可吊销/重置
- 📦 hash-first 增量同步(只传变更)
- 🎚️ RAG 同步模式(auto / manual + 文档级勾选)
- 🌍 界面中英文切换
- 🌲 知识库三栏树形浏览(节点 → 目录树 → 文档)
- 🔌 Node 本地 MCP 代理(`akm-node --mcp`,智能体零配置接入)

完整迭代计划见 [docs/product-overview.md](docs/product-overview.md)。

## 架构

```
                ┌─────────────────────────────┐
                │   Hub(FastAPI)              │
                │   Web UI + REST API + WS    │
                │   关键词⊕语义混合检索          │
                │   MCP / Context API         │
                └──────────┬──────────────────┘
                     WebSocket / HTTP
        ┌───────────────────┼───────────────────┐
   Node-Mac            Node-Windows          Node-Linux
  (本地 Markdown)      (本地 Markdown)       (本地 Markdown)
```

| 层 | 技术 |
| --- | --- |
| Hub 后端 | Python 3.11 + FastAPI + SQLAlchemy(async) |
| 数据库 | SQLite(零配置)/ PostgreSQL(pgvector 向量) |
| 前端 | React 18 + Vite + TypeScript |
| 通信 | WebSocket + HTTP(JSON) |
| 包管理 | uv(Python)/ npm(前端) |

```
AgentKnowledgeMesh/
├── src/server/   # Hub 后端    ├── src/node/   # Node 客户端
├── src/web/      # React 前端  ├── src/shared/ # 共享扫描器
├── docs/         # 产品/技术文档与规约
└── openspec/     # 规范驱动开发工件
```

## 快速启动

前置:Python 3.11+、Node.js 20+、[uv](https://docs.astral.sh/uv/)(`curl -LsSf https://astral.sh/uv/install.sh | sh` 或 Windows `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)。

### 1)Hub 后端

```bash
cd src/server
uv sync
cp .env.example .env    # 零配置可直接用(SQLite + 本地嵌入模型,首次运行下载模型)
uv run akm-hub          # http://localhost:8000
```

### 2)Web 界面(开发模式)

```bash
cd src/web
npm install
npm run dev             # http://localhost:5173(已代理 /api → :8000)
```

生产部署:`npm run build` 后把 `dist` 交由 Nginx/Docker 托管(Hub 静态托管目录统一见 docs/technical-design.md §8)。

### 3)节点接入(另一台电脑)

```bash
cd src/node
uv sync
uv run akm-node login   # 交互输入 Hub 地址与管理员账号,凭证写入本地 .env
uv run akm-node         # 无头常驻:注册、心跳、hash-first 增量同步本地文档
```

> 首次启动 Hub 会自动创建管理员账号(默认用户名 `admin`,随机密码打印在启动日志;可用 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` 环境变量指定)。忘记密码可在 Hub 所在机器执行 `uv run akm-hub reset-password <username>`。
>
> 知识库目录仍通过节点本地 `.env` 的 `AKM_KNOWLEDGE_ROOTS` 配置(参考 `src/node/.env.example`)。
>
> 同步为 hash-first 增量:首轮全量上传,之后未变更文档仅上报 path+hash,删除显式走 `deletions`;快照存于 `src/node/data/sync_state.json`(已 gitignore),删除它可在下轮强制全量重建。协议细节见 [docs/api-reference.md §8](docs/api-reference.md)。

### Docker

```bash
KNOWLEDGE_DIR=~/Knowledge docker compose up -d        # Hub(SQLite)
docker compose -f docker-compose.pg.yml up -d         # Hub(PostgreSQL)
docker compose -f docker-compose.node.yml up -d       # Node
```

正式部署(拉取 GHCR 发布镜像 + 各机器一键安装 akm-node)见 **[docs/deployment.md](docs/deployment.md)**。

## 使用说明

- **浏览知识库**:Web 首页看统计;知识库页三栏布局(左选节点 → 中文件树 → 右渲染),搜索命中自动展开到对应文档,展开状态按节点记忆
- **搜索**:顶栏实时搜索 = 关键词检索;语义检索走 `/api/rag/search`(或界面检索入口)
- **文档进 RAG**:默认 auto 模式,节点文档与本地扫描的文档自动进入向量库;设置页可切 manual(新文档默认 excluded,仅手动勾选参与语义检索,文档树中 ⛔ 徽标可点击单篇加入/移出,顶部+/-批量操作)。语义检索与关键词临界见设置页说明
- **AI 工具接入(MCP)**:推荐方式 —— 机器上装有节点时,智能体直接用本地节点做 MCP 入口(免配 Hub 地址与凭证;凭证只留节点本机):

```json
{
  "mcpServers": {
    "agentknowledge": {
      "command": "uv",
      "args": ["run", "akm-node", "--mcp"],
      "cwd": "src/node"
    }
  }
}
```

一键安装版(`deploy/install-akm-node.*`,见部署文档)直接用全局命令,无需 cwd:

```json
{ "mcpServers": { "agentknowledge": { "command": "akm-node", "args": ["--mcp"] } } }
```

节点代理经 stdio 提供与 Hub 同名的三个工具(`search_documents` / `get_document` / `list_documents`),内部转调 Hub HTTP API(统一 10s 超时);`search_documents` 支持 `mode=semantic` 走 Hub 语义混合检索(向量⊕关键词按权重融合);节点本地无凭证(未执行过 `akm-node login`)时会输出"请先执行 akm-node login"并退出。

远程/无节点机器用 Hub:SSE 模式 `"url": "http://localhost:8000/api/mcp/sse"`(需在 Web「设置」页创建 API Token),或 Hub 本机 stdio 模式 `"command": "uv", "args": ["run", "akm-hub", "--mcp"]`。三种接入形态工具集与返回格式完全一致。测试:`npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/sse`。

- **Agent 检索接口**:`GET /api/context?q=xxx`(需 API Token)
- **节点接入**:`uv run akm-node login` 输入账号密码 → 换取节点 token → 无头常驻;Web 端可吊销/重置(见 §3「节点接入」)

## 配置

两个组件各有一份模板:`src/server/.env.example`、`src/node/.env.example`,复制为 `.env` 后按需修改。常用项:

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AKM_PORT` | `8000` | Hub 端口 |
| `AKM_DB_TYPE` | `sqlite` | `sqlite` / `postgres` |
| `AKM_KNOWLEDGE_ROOTS` | `~/Knowledge` | 知识库目录(逗号分隔多个) |
| `AKM_EMBEDDING_PROVIDER` | 模板内 `local` | `local`(离线)/ `ark`(火山引擎,中文更好) |
| `AKM_HUB_URL`(node) | `ws://localhost:8000/ws` | Hub 地址 |

完整配置与混合检索调优参数见模板文件内注释。

## 文档索引

- [docs/product-overview.md](docs/product-overview.md) — 产品概要与迭代计划
- [docs/technical-design.md](docs/technical-design.md) — 当前批次技术方案
- [docs/api-reference.md](docs/api-reference.md) — API 参考
- [docs/deployment.md](docs/deployment.md) — 部署指南(容器 Hub / akm-node 一键安装)
- [docs/conventions/](docs/conventions/) — UI / 流程 / 文件规范
- [AGENTS.md](AGENTS.md) — 工程规约地图(AI 会话入口)

## License

MIT
