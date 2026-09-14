# 技术方案 · V0.4 账号与治理

> 本文档是 V0.4 批次(见 [product-overview.md](product-overview.md) §3)的技术设计,是 openspec 变更的输入。
> 状态:设计已评审要点 —— 账号体系 = admin+viewer 两级;节点接入 = CLI 登录换 token;RAG 模式 = 全局开关 + 文档级勾选;静态目录 = **待定不实施**。

## 1. 总览

### 1.1 现状基线(与本批相关的部分)

| 领域 | 现状 | 问题 |
| --- | --- | --- |
| Web API | 全部端点无鉴权(仅 `PUT /api/nodes/{id}/documents` 校验 Bearer token) | 读写全裸(#2) |
| 节点接入 | WS 连上即注册,HUB 返回 `uuid4().hex` token 永久复用 | 无生命周期、可任意伪造注册(#3) |
| 节点同步 | Node 每次 `PUT` 上传**全部文档全文** | 流量 O(全部字节)(#5) |
| RAG | 节点文档:上传后自动增量向量化;本地扫描:只入库,需手动 `POST /api/rag/index` 全量重建 | 无模式开关、无文档级控制 |
| 前端 | 文案硬编码中文;知识库页无节点/树形维度 | i18n、树形浏览缺失 |
| 静态托管 | Hub 只认 `src/server/static/`,构建产物在 `src/web/dist/` | 目录不一致(待定 §8) |

### 1.2 变更清单与 openspec 拆分

| 变更目录(拟) | 覆盖 | 涉及 |
| --- | --- | --- |
| `add-account-auth` | §2 + §3(含 #2 #3) | server 全端点 + node CLI + web 登录页 |
| `add-hash-first-node-sync` | §4(#5) | node sync + server nodes API |
| `add-rag-sync-modes` | §5 | server RAG/indexer + web 设置页/文档操作 |
| `add-web-i18n` | §6 | web 全部文案 |
| `add-kb-tree-layout` | §7 | web Knowledge 页 + server tree API |
| `add-node-mcp-proxy` | §9 | node 新增 `--mcp` 代理模式 + server 鉴权矩阵(node token 只读) |

---

## 2. 账号与鉴权(admin / viewer)

### 2.1 数据模型

```
users: id(PK), username(unique), password_hash, role("admin"|"viewer"),
       disabled(bool, default false), created_at, updated_at
api_tokens: id(PK), name, token_hash(sha256), role("viewer"|"admin"),
            created_by, created_at, last_used_at, revoked_at(nullable)
```

- 密码哈希:`bcrypt`(新增依赖 `passlib[bcrypt]`;若引入成本高,退而用 `hashlib.pbkdf2_hmac` 自实现,二选一在 proposal 定稿)
- API Token 供 Agent/脚本长期使用;**只存哈希**,明文仅在创建/轮换时返回一次
- API Token 生命周期:`create` → `rotate`(同一记录换发新密钥,旧密钥立即失效,不留"已吊销"记录) → `revoke`(软删,保留 `revoked_at` 审计) → `purge`(硬删,仅限已吊销)

### 2.2 初始化

- 首次启动且 `users` 表为空时:
  - `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` 已设置 → 创建 admin
  - 未设置 → 生成随机密码,打印到启动日志一次(带"请尽快登录修改"提示)
- 端点:`POST /api/auth/change-password`(本人)、`POST/GET/DELETE /api/auth/users`(admin 管理用户)

### 2.3 会话与凭证

| 凭证 | 用途 | 形态 | 有效期 |
| --- | --- | --- | --- |
| JWT | Web 登录会话 | `POST /api/auth/login` → `{access_token}`;HS256;`AKM_SECRET_KEY`(未配置则首次生成存 `data/secret.key`) | 24h,无刷新(过期重登,P1 足够) |
| API Token | Agent/脚本调 Context API、MCP SSE | `Authorization: Bearer akm_xxx` | 永久,可轮换/吊销 |
| Node Token | 节点机器身份(§3) | 节点本地凭证文件 | 永久,可吊销/重置 |

### 2.4 端点保护矩阵

| 端点组 | 免鉴权 | viewer | admin |
| --- | --- | --- | --- |
| `GET /api/health`、`/api/auth/*`(login) | ✅ | — | — |
| 其余全部 `GET /api/**` | — | ✅ | ✅ |
| 文档写(PUT/POST 编辑、scan、RAG index、RAG 勾选) | — | ❌ 403 | ✅ |
| 节点管理(删除节点、重置 token)、`/api/nodes/*/sync` | — | ❌ | ✅ |
| 用户管理、API Token 管理 | — | ❌ | ✅ |
| WS `/ws`(节点) | 走 §3 的 node token 校验,不走 JWT | | |

实现:FastAPI dependency `require_auth(min_role)` 注入各路由;`/api/context`、`/api/mcp/sse` 接受 JWT **或** API Token。

> 节点凭证(node token)授权范围:仅**只读**知识端点(`GET /api/search`、`/api/rag/search`、`/api/context`、`/api/documents` 读取类),供节点本地 MCP 代理使用(§9.2);不得访问用户管理、写操作与其他节点数据。

### 2.5 前端

- 新增登录页;401 → 跳登录;`api/client.ts` 统一注入 `Authorization` 头、统一处理 401/403
- token 存 `localStorage`(键 `akm.auth`);侧栏底部显示当前用户与登出
- viewer 角色隐藏/禁用写操作入口(前端隐藏只是体验,权限以服务端为准)

---

## 3. 节点 CLI 登录接入

### 3.1 登录流(首次接入 / 重新认证)

```
节点机                                    Hub
  │ akm-node login                         │
  │  → 提示输入 Hub URL / 用户名 / 密码      │
  │ ── POST /api/auth/login ─────────────▶ │ (需 admin 账号)
  │ ◀─ access_token ────────────────────── │
  │ ── POST /api/nodes/register ─────────▶ │ {node_name, platform}
  │    (Authorization: JWT)                │ 创建/更新 nodes 记录,
  │                                        │ 轮换生成新 node_token
  │ ◀─ {node_id, node_token} ───────────── │
  │ 写入节点本地 .env:                      │
  │   AKM_NODE_ID / AKM_NODE_TOKEN         │
  ▼                                        │
后续 uv run akm-node 无头启动,携带 token 声明身份
```

### 3.2 协议变更

- WS `register` 消息增加 `token` 字段;Hub 校验 `node_id + token` 与库中一致才 `register_ack`,否则回 `{type:"error"}` 并关闭(4001)
- **不再接受匿名注册**(未带 token 的一律拒绝)—— 解决"任何知道地址的客户端都能注册"的问题
- 节点请求头/消息均带 token;PUT 上传沿用现有 Bearer node token

### 3.3 token 生命周期(#3 的解法)

| 能力 | 入口 | 行为 |
| --- | --- | --- |
| 吊销 | Web 节点页「禁用」 | `nodes.status=revoked`;该节点 WS/PUT 立即 401 |
| 重置(轮换) | Web 节点页「重置 token」 | 生成新 token,旧 token 失效;节点需重新 `akm-node login`(或 Web 复制新 token 手工下发) |
| 过期(可选) | `akm-node login --expires-days N` | 默认永久;P1 不做自动清理,仅注册时校验 |

---

## 4. hash-first 节点同步(#5)

### 4.1 节点侧

- 本地状态文件 `<data>/sync_state.json`:`{ "<path>": "<hash>" }`(上次已确认同步的快照)
- 每轮同步:扫描 → 与快照 diff → 分类:
  - `added` / `changed`:上传**含 content**
  - `unchanged`:只报 `{path, hash}`,**不带 content**
  - `removed`:进 `deletions` 列表
- 收到 Hub 200 后用当轮扫描结果更新快照(失败不动快照,下轮重试)

### 4.2 协议(`PUT /api/nodes/{id}/documents`)

```json
{
  "documents": [
    {"path": "a.md", "title": "A", "hash": "…", "size": 123, "content": "…"},
    {"path": "b.md", "hash": "…"}
  ],
  "deletions": ["c.md"]
}
```

Hub 端 `_sync_node_documents` 规则:

- 携带 `content` → 按现有 hash 比对入库(现状逻辑不变)
- 未携带 `content` → 若库中该 `(node_id, path)` 的 hash 一致则忽略;不一致则该条计为 `rejected` 并在响应中列出(节点下轮会带 content 重传)
- `deletions` → 删除对应文档并派发向量清理(复用现有 `deleted_ids` 通道)

### 4.3 兼容性

旧版节点继续发全量 content → Hub 照常处理;协议向后兼容,节点端先升。

---

## 5. RAG 同步模式(全局开关 + 文档级勾选)

### 5.1 模型与语义

```
app_settings: key(PK), value(text), updated_at
  └─ rag_sync_mode = "auto" | "manual"   (默认 auto)

documents 新增列: rag_status TEXT  ("pending"|"indexed"|"excluded")
  存量迁移默认 = "indexed"(保持现有可检索性);此后新文档由模式决定:
  auto 模式新文档 = "pending"(索引完成后转 indexed),manual 模式新文档 = "excluded"
```

| 场景 | auto 模式 | manual 模式 |
| --- | --- | --- |
| 节点上传变更文档 | 新文档 `pending` → 后台向量化 → `indexed` | `excluded`(不入向量库) |
| 本地扫描变更文档 | 同上(**打通现状缺口:本地扫描也自动**) | 同上 |
| 文档级「加入 RAG」 | 强制 `pending` → 索引 | 同左 |
| 文档级「移出 RAG」 | `excluded` + 删除该 doc 向量分块 | 同左 |
| `POST /api/rag/index` | 全量重建(保留,admin) | 只重建 `rag_status != "excluded"` 的文档 |
| 语义检索 | 只召回 `indexed` | 只召回 `indexed` |

### 5.2 API 增量

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/settings` | 读设置(admin/viewer) | viewer |
| PUT | `/api/settings` | 改设置,如 `{"rag_sync_mode":"manual"}`(切换为 manual 时不清已有向量;切回 auto 时把 `excluded` 之外的文档补齐索引) | admin |
| PUT | `/api/documents/{id}/rag` | `{"enabled": true|false}` 单篇勾选 | admin |
| POST | `/api/documents/rag/batch` | `{"doc_ids":[…],"enabled":bool}` 批量 | admin |

### 5.3 实现要点

- 抽公共服务 `services/rag/sync.py`:`index_documents(doc_ids)` / `remove_documents(doc_ids)`,节点上传通道与本地扫描通道共用(替代 nodes.py 内嵌的 `_sync_vectors`)
- documents 列表/详情响应带 `rag_status`;列表支持 `?rag_status=` 过滤
- 前端:设置页加 RAG 模式开关;文档列表加状态列与单篇/批量操作

---

## 6. Web 中英文切换

- 方案:`react-i18next` + `i18next`,`src/web/src/i18n/` 下 `zh.ts` / `en.ts` 两个语言包,`index.ts` 初始化(默认 `zh`,回退 `zh`)
- 切换入口:侧栏底部 `中文 / EN` 切换;选择持久化 `localStorage(`akm.lang`)`
- 规约:**组件内禁止硬编码用户可见文案**,一律 `t("ns.key")`;命名空间按页面/领域划分(nav、auth、dashboard、knowledge、nodes、settings、common)
- 时间等本地化:现有 ISO 字符串展示保持不变(P1 不引入日期库)

---

## 7. 知识库三栏树形浏览

### 7.1 布局与交互

```
┌──────────┬───────────────┬──────────────────────────┐
│ 节点列表  │  文档树(中栏)   │  文档渲染(右栏)             │
│ (现有     │  ▸ 目录/…      │  MarkdownViewer            │
│  NodeList │  ▾ 知识库/     │  未选中时显示占位引导          │
│  收窄复用) │    ├ a.md      │                            │
│          │    └ b.md      │                            │
└──────────┴───────────────┴──────────────────────────┘
```

- 选节点 → 中栏加载该节点文档树;**默认全部收起**,目录可展开/收起(含「全部展开/收起」快捷)
- 展开状态按节点记忆(`localStorage`,键 `akm.tree.<node_id>`)
- 点选文档 → 右栏渲染;顶栏全局搜索命中后联动选中并展开路径
- 中宽屏以下(<1024px)退化为两栏:树与文档叠加/切换

### 7.2 API 增量

`GET /api/documents/tree?node_id=<id>`:按节点过滤;不带参数返回全部(兼容)。`FileTree` 组件复用并增强(受控展开态、点击目录折叠)。

---

## 8. 待定:静态托管目录统一(本轮不实施)

**现状**:Hub 启动时若发现 `src/server/static/` 存在则托管为站点根(`:8000` 直接访问前端,生产部署单进程);但前端构建产物在 `src/web/dist/`,目录不一致导致 `:8000` 404,本地需手动拷贝或另跑 vite。

**候选**(想清楚后另开变更):

| 候选 | 做法 | 评价 |
| --- | --- | --- |
| A. env 指向 dist | `AKM_STATIC_DIR` 默认 `../web/dist`,免拷贝 | 依赖仓库相对结构,Docker 需覆盖 |
| B. env 默认 static + 构建后拷贝 | Makefile 自动 `dist → static` | hub 目录自包含,多一步拷贝 |
| C. 三级回退 | env > web/dist > static | 灵活但排障不直观 |

---

## 9. MCP / 智能体接入形态

### 9.1 形态总览

| 接入点 | 命令/端点 | 场景 | 凭证 |
| --- | --- | --- | --- |
| **Node 本地 MCP(默认)** | 智能体配置 spawn:`uv run akm-node --mcp` | 装了 akm-node 的机器上的智能体(主力路径) | 节点本地 `.env` 凭证;对 Hub 出示 node token |
| Hub SSE(远程/补充) | `http://<hub>:8000/api/mcp/sse` | 未装节点的机器、服务端智能体 | API Token |
| Hub stdio(本机调试) | `uv run akm-hub --mcp` | Hub 本机直连库场景 | 本机信任,免鉴权 |

设计原则:**智能体永远只配"一条本地命令或一个 URL"**,Hub 的地址与凭证只存在于节点本机。

### 9.2 Node 本地 MCP 代理(新增)

- 形态:stdio(`akm-node --mcp`),智能体拉起子进程,无需常驻端口;不需要额外的守护进程
- 实现:轻量代理 —— 三个工具与 Hub MCP 同名同参,内部转调 Hub HTTP API(复用节点已有 httpx 与凭证):

  | MCP 工具 | 转调 |
  | --- | --- |
  | `search_documents` | `GET /api/search`(可扩展 `mode=semantic` → `GET /api/rag/search`) |
  | `get_document` | `GET /api/documents/{id}` |
  | `list_documents` | `GET /api/documents` |

- 凭证:`akm-node login` 写入的 `AKM_NODE_ID` / `AKM_NODE_TOKEN`;Hub 侧授权 node token **只读**知识端点(§2.4 补充)
- Hub 不可达时返回明确错误信息;V1.0 备选:离线降级(本地文件现扫 + 关键词匹配)
- **节点不做第二检索引擎**:节点无索引无向量,语义质量必须由 Hub 保证;节点只做"就近入口"

### 9.3 决策

1. Node 本地 MCP 代理为智能体接入的**默认形态**:节点已随机器部署,智能体免配 Hub 地址/凭证
2. Hub SSE 保留:远程/无节点场景;API Token 鉴权
3. 不做独立 CLI 检索(`akm search`):MCP 已覆盖
4. 智能体侧**无需**我们实现 MCP 客户端 —— Claude Code 等工具自带 host 能力,只需配置

## 10. 测试与验收

- **server**:`uv run pytest` —— 新增:鉴权矩阵(401/403 逐组)、用户与 token 生命周期、节点 register 带token/匿名拒绝、hash-first 协议(content 缺省/rejected)、RAG 模式切换与文档级勾选、tree node_id 过滤
- **node**:登录流(e2e 手册)+ 状态文件 diff 单测
- **web**:`npm run build` 通过;手测:登录/403 遮罩、语言切换、三栏树交互、RAG 勾选
- **回归**:既有 31 个测试保持通过;V0.3 语义/关键词检索行为不回退
