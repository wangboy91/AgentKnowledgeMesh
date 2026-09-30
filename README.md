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
- ⌨️ 节点 CLI 登录接入(`akm-node login`,登录成功即自动连接并首次同步),token 可吊销/重置;`--help` 说明命令与断线重连行为;无人值守场景可用 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 启动即自动登录
- 📦 hash-first 增量同步(只传变更)
- 👁 文件变更实时监听(改动数秒内同步到 Hub)+ 定时对账兜底
- 🎚️ RAG 同步模式(auto / manual + 文档级勾选)
- 🌍 界面中英文切换
- 🌲 知识库三栏树形浏览(节点 → 目录树 → 文档)
- 🔌 Node 本地 MCP 代理(`akm-node --mcp`,智能体零配置接入)
- ✍️ 智能体写回(MCP `create_document` / `update_document`;节点凭证可写但作用域限本节点,写回内容立即进入检索与多机分发)

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

生产部署:`npm run build` 后由 Hub 托管 `dist`(镜像构建时自动拷到 `/app/static`,见 `src/Dockerfile`;静态托管细节见 docs/technical-design.md §8)。

> ⚠️ **`index.html` 必须经 Hub 返回**:Hub 会在其中注入部署前缀(`<base href>` + `window.__AKM_BASE__`),前端据此确定路由 basename 与 API 基址。因此不要把 `dist` 单独交给 Nginx 托管 —— 反代只需把整个前缀转发给 Hub(见 [docs/deployment.md §1.9](docs/deployment.md))。前端产物本身用相对基路径构建,同一份产物可部署在任意深度子路径下,无需重新构建。

### 3)节点接入(另一台电脑)

```bash
cd src/node
uv sync
uv run akm-node login   # 交互输入 Hub 地址与管理员账号;成功后自动连接并首次同步
uv run akm-node --help  # 命令一览:用法、断开(Ctrl+C)与断线重连(5 秒)说明
```

> `akm-node login` 一条命令完成「换取凭证 → 连接 Hub → 首次扫描同步」,随后前台常驻;断开按 Ctrl+C。之后再启动只需 `uv run akm-node`(无凭证时会提示先登录)。

> **无人值守部署**(systemd / 计划任务 / 容器)可改用环境变量免交互接入:在节点配置里填 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD`(Hub 管理员账号),启动时若本地还没有节点凭证就会自动登录换取并写回 `~/.akm-node/.env`;已有凭证时直接使用、不再登录。凭证落盘后即可把密码移出配置(明文存放,注意权限)。两种方式等价,`akm-node login` 交互登录始终可用。

> 首次启动 Hub 会自动创建管理员账号(默认用户名 `admin`,随机密码打印在启动日志;可用 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` 环境变量指定)。忘记密码可在 Hub 所在机器执行 `uv run akm-hub reset-password <username>`。
>
> 知识库目录仍通过节点本地 `.env` 的 `AKM_KNOWLEDGE_ROOTS` 配置(参考 `src/node/.env.example`)。
>
> 同步为 hash-first 增量:首轮全量上传,之后未变更文档仅上报 path+hash,删除显式走 `deletions`;快照存于 `src/node/data/sync_state.json`(已 gitignore),删除它可在下轮强制全量重建。协议细节见 [docs/api-reference.md §8](docs/api-reference.md)。
>
> 上传会按体积(默认 512 KiB)与条数(默认 50)自动切分为多个请求,因此知识库规模不受 Hub 前置反向代理 body 上限约束——即便 nginx 用默认的 `client_max_body_size 1m`,首次接入大知识库也不会 413(`AKM_UPLOAD_BATCH_*` 可调,内网直连可调大以减少请求数)。
>
> 节点常驻时会**监听知识库目录**,文件改动数秒内同步到 Hub(防抖默认 3 秒),另每 300 秒做一次全量对账兜底(监听可能丢事件)。只同步 `.md`,`.git` / `node_modules` / `dist` 等目录自动跳过;四个配置项(`AKM_WATCH_*`)与后台常驻模板见 [docs/deployment.md §2.5](docs/deployment.md)。容器 / bind mount 场景监听不可用,自动依赖对账。
>
> ⚠️ 同步是**单向**的:各节点把文档推给 Hub,其他电脑的智能体经 MCP / Web 查询 Hub 拿到最新内容;文档不会下发到各节点本地磁盘。

### Docker

```bash
# 方式一:拉取 GHCR 发布镜像(默认)
docker compose -f deploy/docker-compose.yml up -d               # Hub(SQLite,无 RAG)
docker compose -f deploy/docker-compose.pg.yml up -d            # Hub(PostgreSQL + pgvector,含 RAG)
docker compose -f deploy/docker-compose.external-pg.yml up -d   # Hub(外接已有 PostgreSQL,含 RAG)

# 方式二:从当前源码构建镜像(不想等发版 / 要改源码 / 要装发布镜像不含的可选依赖 / 内网拉不到 GHCR)
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.build.yml up -d --build

# 节点容器(可选:知识源机器本身是 Docker 环境;需先登录,见部署文档 §2.4)
docker compose -f deploy/docker-compose.node.yml up -d --build
```

> 部署配置统一在 `deploy/`,两种方式配置完全一致,只有镜像来源不同(`KNOWLEDGE_DIR`、管理员账号、Ark 嵌入等变量见 [docs/deployment.md §1.3](docs/deployment.md));源码构建可用 `AKM_UV_EXTRAS=local-embedding` 装离线本地嵌入模型(见 [§1.8](docs/deployment.md))。节点默认是每台知识源机器一条命令安装的轻量客户端(见上方「节点接入」),不想装宿主命令时可改用上面的节点容器。

> **要挂在前置路由的子路径下**(如 `https://xx.com/akm/`、`https://xx.com/akm-hub/`,任意层级)?设 `AKM_ROOT_PATH=/akm` 并在反代转发该前缀即可 —— 前缀叫什么、多少层都不需要改镜像或重新构建前端。配置见 [docs/deployment.md §1.9](docs/deployment.md)。

> ⚠️ **RAG(语义检索/向量化)依赖 PostgreSQL + pgvector,SQLite 模式不支持**:SQLite 模式下语义检索接口与 MCP `mode=semantic` 降级为关键词检索、向量化无法开启(设置页开启时提示向量库初始化失败);关键词检索与文档同步不受影响。需要 RAG 请用 PostgreSQL 模式。另:向量化**默认关闭**,需在设置页开启。详见 [docs/deployment.md §1.2](docs/deployment.md)。

正式部署(拉取 GHCR 发布镜像 + 各机器一键安装 akm-node)见 **[docs/deployment.md](docs/deployment.md)**。

## 使用说明

- **浏览知识库**:Web 首页看统计;知识库页三栏布局(左选节点 → 中文件树 → 右渲染),搜索命中自动展开到对应文档,展开状态按节点记忆
- **搜索**:顶栏实时搜索 = 关键词检索;语义检索走 `/api/rag/search`(或界面检索入口)
- **向量化(默认关闭)**:升级后向量化**默认不启用**——不初始化向量库、不产生任何嵌入调用,语义检索自动降级为关键词检索(关键词搜索始终可用)。需要语义检索时在**设置页开启「向量化」**(开启时先校验向量库连接,失败则保持关闭)
- **文档进 RAG**:向量化开启后,由「RAG 同步模式」决定是否自动入库——`manual`(默认)= 新文档标记 `not_indexed`,需手动加入;`auto` = 新/变更文档自动向量化。手动入口:文档树中 ⛔/⊖ 徽标点击单篇加入/移出,顶部 +/- 批量操作,或「全量索引 RAG」一次性纳入所有未向量化文档(跳过已移出的)。语义检索与关键词临界见设置页说明
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

节点代理经 stdio 提供与 Hub 同名的**五个**工具:只读 `search_documents` / `get_document` / `list_documents`,以及写回 `create_document` / `update_document`,内部转调 Hub HTTP API(统一 10s 超时);`search_documents` 支持 `mode=semantic` 走 Hub 语义混合检索(向量⊕关键词按权重融合,**需 Hub 为 PostgreSQL 模式**);节点本地无凭证(未执行过 `akm-node login`)时会输出"请先执行 akm-node login"并退出。

**智能体写回**:`create_document(path, content, title?)` 新建、`update_document(document_id, content)` 覆盖更新。经节点代理写入时,文档归属该节点(`node_id` 由 Hub 依节点凭证强制,代理无法指定),且只能更新本节点名下的文档(跨节点 403);经 Hub stdio/SSE 写入时归属 `local`。路径唯一性按 `(node_id, path)` 判定——不同机器的同名路径可共存。写回内容立即进入检索与多机分发,其他电脑的智能体随即检索得到。写回**不落本地磁盘**(文档只存在于 Hub),也不会删除任何文档。详见 [docs/agent-write-back-design.md](docs/agent-write-back-design.md)。

远程/无节点机器用 Hub:SSE 模式 `"url": "http://localhost:8000/api/mcp/sse"`(需在 Web「设置」页创建 API Token),或 Hub 本机 stdio 模式 `"command": "uv", "args": ["run", "akm-hub", "--mcp"]`。三种接入形态工具集与返回格式完全一致。测试:`npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/sse`。

- **Agent 检索接口**:`GET /api/context?q=xxx`(需 API Token)
- **节点接入**:`uv run akm-node login` 输入账号密码 → 换取节点 token → 自动连接 Hub 并首次同步(前台常驻,Ctrl+C 退出);Web 端可吊销/重置(见 §3「节点接入」)。免交互场景改用 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 配置账号,启动即自动登录

## 配置

两个组件各有一份模板:`src/server/.env.example`、`src/node/.env.example`,复制为 `.env` 后按需修改。常用项:

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AKM_PORT` | `8000` | Hub 端口 |
| `AKM_DB_TYPE` | `sqlite` | `sqlite` / `postgres`(**RAG 语义检索仅 postgres,需 pgvector**) |
| `AKM_KNOWLEDGE_ROOTS` | `~/Knowledge` | 知识库目录(逗号分隔多个) |
| `AKM_EMBEDDING_PROVIDER` | 模板内 `local` | `local`(离线)/ `ark`(火山引擎,中文更好) |
| `AKM_HUB_URL`(node) | `ws://localhost:8000/ws` | Hub 地址 |
| `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD`(node) | 空 | 可选;配齐后节点启动时自动登录换取凭证(无凭证时生效) |
| `AKM_UPLOAD_BATCH_BYTES` / `AKM_UPLOAD_BATCH_DOCS`(node) | `524288` / `50` | 上传分批的单请求体上限(字节)/ 条数上限;置 0 或负数为不限 |

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
