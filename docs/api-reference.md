# API 参考 · AgentKnowledgeMesh

> 运行中的完整接口清单以 `http://localhost:8000/docs`(FastAPI Swagger)为准;本文按领域归档要点。标注 🆕 的是已规划待实现接口(见 [technical-design.md](technical-design.md)),已实现的不再标注。

> **子路径部署**:服务挂在反向代理前缀下时(如 `https://xx.com/akm/`),下表所有路径都要加上前缀 —— `/api/health` → `/akm/api/health`,`/ws` → `/akm/ws`,以此类推,前缀由 `AKM_ROOT_PATH` 决定(任意层级)。Swagger 的 `servers` 也会自动带上该前缀。配置方式见 [deployment.md §1.9](deployment.md)。

## 1. 鉴权

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录,返回 JWT(24h) | 公开 |
| POST | `/api/auth/change-password` | 修改本人密码 | 登录用户 |
| GET/POST/PUT/DELETE | `/api/auth/users` | 用户管理(创建/禁用/改角色/重置密码/删除) | admin |
| GET/POST/DELETE | `/api/auth/tokens` | API Token 管理(创建仅返回一次明文/吊销软删/彻底删除已吊销) | admin |
| POST | `/api/auth/tokens/{id}/rotate` | 轮换 Token:同一记录换发新密钥,旧密钥立即失效,不产生"已吊销"残留(明文仅本次返回) | admin |

> 除 `GET /api/health` 与 auth 外,全部端点需要 `Authorization: Bearer <JWT|API Token|节点token>`;viewer 只读,admin 可写。Agent/脚本用 API Token 调 Context API 与 MCP SSE。节点凭证(node token)另享**只读**知识端点权限(search / rag/search / context / documents 读取类),以及**受限写权限**:`POST /api/documents` 与 `PUT /api/documents/:id` 放行,但作用域限本节点(创建的文档归属该节点,仅能更新 `node_id` 等于该节点的文档,跨节点 403)。其余写端点(扫描、节点管理)节点凭证仍 403。供节点本地 MCP 代理写回使用(见 [agent-write-back-design.md](agent-write-back-design.md))。首次启动自动创建管理员(环境变量或随机密码打印);本机恢复:`uv run akm-hub reset-password <username>`。

## 2. 系统与文档

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查(免鉴权) |
| GET | `/api/stats` | 系统统计 |
| GET | `/api/documents` | 文档列表(支持 `node_id` / `rag_status` 过滤;🆕 `path` 精确匹配,组合 `node_id` 可唯一定位) |
| GET | `/api/documents/tree?node_id=` | 文件树(🆕 `node_id` 按节点过滤;🆕 `dir` 目录切片:传目录路径(含空串=根)返回该目录**一层直接子项**供前端懒加载,缺省返回完整树;叶子节点携带 `id`) |
| GET | `/api/documents/:id` | 文档详情(含内容) |
| POST | `/api/documents/scan` | 触发本地扫描(admin);🆕 响应含 `skipped`(与 `agent` 来源文档同路径而被跳过的条目数) |
| PUT | `/api/documents/:id` | 编辑文档(admin,或节点凭证且文档归属本节点);🆕 编辑后文档 `origin` 转为 `agent` |
| POST | `/api/documents` | 新建文档(admin,或节点凭证——归属强制为该节点;唯一性按 `(node_id, path)`);🆕 新建文档 `origin` 为 `agent` |

> **🆕 文档内容来源 `origin`**(`2026-09-30-fix-document-persistence`):文档对象新增 `origin` 字段,标识正文的权威来源。
> `file`(默认)——内容由文件扫描派生(Hub 本机目录扫描、节点磁盘上传),磁盘是权威,可被扫描与节点同步覆盖、可因文件消失被删除;
> `agent`——内容由 Hub/智能体写入(`POST /api/documents`、`PUT /api/documents/:id`、MCP `create_document` / `update_document`),无对应磁盘文件,
> Hub 库是权威,**对一切文件来源事件免疫**(不被覆盖、不被删除)。编辑一篇 `file` 文档会把它转为 `agent`,该转换是单向的。
> 详见 [known-issues.md](known-issues.md) 问题 1/2 的修复记录。

## 3. 检索与 RAG

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/search?q=` | 关键词搜索 |
| GET | `/api/context?q=` | Agent 上下文接口(需 JWT、API Token 或节点 token) |
| GET | `/api/rag/search?q=` | 语义/混合检索(🆕 向量化关闭时降级为关键词,响应 `mode` 为 `keyword`) |
| GET | `/api/rag/context?q=` | RAG 上下文(🆕 同上降级) |
| POST | `/api/rag/index` | 全量向量化所有非 `excluded` 文档(admin;🆕 后台派发,响应 `{message, queued}`;向量化关闭时 409) |
| GET | `/api/rag/stats` | 向量库统计(🆕 含 `vectorization_enabled`;关闭时不连向量库) |
| GET/PUT | `/api/settings` 🆕 | 应用设置(`rag_sync_mode` 默认 `manual` / `vectorization_enabled` 默认 `false`;PUT 支持部分更新) |
| PUT | `/api/documents/:id/rag` 🆕 | 单篇加入/移出 RAG(🆕 加入方向在向量化关闭时 409,移出仍放行) |
| POST | `/api/documents/rag/batch` 🆕 | 批量加入/移出 RAG(同上) |

> **向量化总开关**(`vectorization_enabled`,默认关闭):关闭时不初始化向量库、不产生嵌入调用,`/api/rag/search` 与 `/api/rag/context` 降级为关键词检索;开启需在 `PUT /api/settings` 中显式置 `true`(服务端先初始化向量库,失败返回 500 且保持关闭)。
>
> **`rag_status` 四态**:`not_indexed`(尚未向量化,默认)/ `pending`(排队中)/ `indexed`(已入向量库,可被语义检索召回)/ `excluded`(用户显式移出,全量索引与检索均跳过)。仅「向量化开启 + `rag_sync_mode=auto`」时新/变更文档自动置 `indexed`。

## 4. 节点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/nodes` | 节点列表 |
| GET | `/api/nodes/:id` | 节点详情 |
| GET | `/api/nodes/:id/documents` | 节点文档 |
| PUT | `/api/nodes/:id/documents` | 节点文档同步(节点 token;V0.4 起 hash-first 协议,见 §7) |
| POST | `/api/nodes/:id/sync` | 请求节点同步(admin) |
| DELETE | `/api/nodes/:id` | 删除节点(admin) |
| POST | `/api/nodes/register` | 节点首次接入(CLI 登录后换取 node token;admin JWT) |
| POST | `/api/nodes/:id/reset-token` | 重置节点 token(admin),旧 token 立即失效 |
| PUT | `/api/nodes/:id` | 禁用/启用节点(admin),禁用后注册与上传均被拒 |

## 5. 文档转换

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/convert/upload` | 上传转换(PDF/DOCX/HTML) |
| POST | `/api/convert/url` | URL 转 Markdown |

## 6. MCP

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/mcp/sse` | MCP SSE 端点(需 JWT 或 API Token) |
| POST | `/api/mcp/messages` | MCP 消息端点(需 JWT 或 API Token) |
| stdio | `uv run akm-hub --mcp` | 本机 stdio 模式(免鉴权,本机信任) |
| stdio | `uv run akm-node --mcp` | 节点本地代理(节点凭证转调 Hub HTTP) |

工具集(三形态同名同参同输出):

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `search_documents` | `query`(必填)、`mode`(`keyword`/`semantic`)、`limit` | 关键词或语义检索 |
| `get_document` | `document_id`(必填) | 取文档全文 |
| `list_documents` | `node_id`、`limit` | 列出文档 |
| `create_document` | `path`、`content`(必填)、`title` | 新建文档(写回;路径冲突提示改用 update) |
| `update_document` | `document_id`、`content`(必填) | 覆盖更新正文(写回) |

> 写回工具的归属:Hub 形态归属 `local`;节点代理形态由 Hub 依节点凭证强制归属该节点,代理不传递也不允许指定 `node_id`。

## 7. WebSocket 协议(`/ws`)

```jsonc
// 节点 → Hub(V0.4 起必须带 token,匿名注册被拒)
{"type": "register", "node_id": "…", "name": "…", "platform": "…", "token": "…"}
// Hub → 节点
{"type": "register_ack", "node_id": "…", "status": "ok", "token": "…"}
// 其余消息(heartbeat / doc_update / doc_request / doc_response)不变
```

## 8. 节点同步协议(hash-first 增量)

```jsonc
// PUT /api/nodes/{id}/documents
{
  "documents": [
    {"path": "a.md", "title": "A", "hash": "…", "size": 1, "content": "…"}, // 新增/变更:带全文
    {"path": "b.md", "title": "B", "hash": "…", "size": 1}                  // 未变更:仅报元信息,无 content
  ],
  "deletions": ["c.md"]   // 显式删除列表;字段恒携带(可为空数组,是新协议标记)
}
// 响应:{"created": n, "updated": n, "deleted": n,
//        "rejected": [{"path":"…","reason":"…"}],   // hash 不一致且无全文:等节点下轮重传
//        "skipped":  [{"path":"…","reason":"agent origin"}]}  // 🆕 agent 来源文档:跳过且不重传
```

- **入库规则**：带 `content` 的条目按 SHA256 哈希比对插入/更新（哈希未变不重复嵌入）；无 `content` 且库中哈希一致 → 忽略；无 `content` 且哈希不一致或路径不存在 → 计入 `rejected`（原因 `hash mismatch` / `path not found`），不入库。
- **rejected 闭环**：节点把 rejected 条目视为未同步，下一轮自动携带全文重传。
- **🆕 agent 来源免疫**：文档 `origin` 为 `agent` 时，命中该路径的条目一律计入 `skipped`（原因 `agent origin`）——既不覆盖、也**不计入 `rejected`**（计入 rejected 会让节点把该路径移出快照、每轮带全文重传而永不收敛）；`deletions` 与隐式缺失推导同样不删除这类文档。
- **删除语义**：请求显式携带 `deletions` 字段（新协议）时按列表删除、不做隐式推导；字段缺省（旧版全量推送）时保留"列表缺失即删除"的兼容行为。
- **幂等**：节点仅在收到 200 响应后更新本地快照（`<node>/data/sync_state.json`，path → hash）；失败不动快照，下轮按相同差异重试。
