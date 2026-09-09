# API 参考 · AgentKnowledgeMesh

> 运行中的完整接口清单以 `http://localhost:8000/docs`(FastAPI Swagger)为准;本文按领域归档要点。标注 🆕 的是 V0.4 规划接口(见 [technical-design.md](technical-design.md)),尚未实现。

## 1. 鉴权 🆕

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录,返回 JWT | 公开 |
| POST | `/api/auth/change-password` | 修改本人密码 | 登录用户 |
| GET/POST/DELETE | `/api/auth/users` | 用户管理 | admin |

> V0.4 起,除 `GET /api/health` 与 auth 外,全部端点需要 `Authorization: Bearer <JWT|API Token>`;viewer 只读,admin 可写。Agent/脚本用 API Token 调 Context API 与 MCP SSE。节点凭证(node token)另享**只读**知识端点权限(search / rag/search / context / documents 读取类),供节点本地 MCP 代理使用(见 [technical-design.md §9](technical-design.md))。

## 2. 系统与文档

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查(免鉴权) |
| GET | `/api/stats` | 系统统计 |
| GET | `/api/documents` | 文档列表(支持分页/过滤) |
| GET | `/api/documents/tree?node_id=` | 文件树(🆕 `node_id` 按节点过滤) |
| GET | `/api/documents/:id` | 文档详情(含内容) |
| POST | `/api/documents/scan` | 触发本地扫描 |
| PUT | `/api/documents/:id` | 编辑文档 |
| POST | `/api/documents` | 新建文档 |

## 3. 检索与 RAG

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/search?q=` | 关键词搜索 |
| GET | `/api/context?q=` | Agent 上下文接口(🆕 需 JWT 或 API Token) |
| GET | `/api/rag/search?q=` | 语义/混合检索 |
| GET | `/api/rag/context?q=` | RAG 上下文 |
| POST | `/api/rag/index` | 全量重建向量索引 |
| GET | `/api/rag/stats` | 向量库统计 |
| GET/PUT | `/api/settings` 🆕 | 应用设置(含 `rag_sync_mode`) |
| PUT | `/api/documents/:id/rag` 🆕 | 单篇加入/移出 RAG |
| POST | `/api/documents/rag/batch` 🆕 | 批量加入/移出 RAG |

## 4. 节点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/nodes` | 节点列表 |
| GET | `/api/nodes/:id` | 节点详情 |
| GET | `/api/nodes/:id/documents` | 节点文档 |
| PUT | `/api/nodes/:id/documents` | 节点文档同步(节点 token;V0.4 起 hash-first 协议,见 §7) |
| POST | `/api/nodes/:id/sync` | 请求节点同步 |
| DELETE | `/api/nodes/:id` | 删除节点 |
| POST | `/api/nodes/register` 🆕 | 节点首次接入(CLI 登录后换取 node token) |
| POST | `/api/nodes/:id/reset-token` 🆕 | 重置节点 token(admin) |

## 5. 文档转换

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/convert/upload` | 上传转换(PDF/DOCX/HTML) |
| POST | `/api/convert/url` | URL 转 Markdown |

## 6. MCP

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/mcp/sse` | MCP SSE 端点(🆕 需 API Token) |
| POST | `/api/mcp/messages` | MCP 消息端点 |
| stdio | `uv run akm-hub --mcp` | 本机 stdio 模式(免鉴权,本机信任) |

## 7. WebSocket 协议(`/ws`)

```jsonc
// 节点 → Hub(V0.4 起必须带 token,匿名注册被拒)
{"type": "register", "node_id": "…", "name": "…", "platform": "…", "token": "…"}
// Hub → 节点
{"type": "register_ack", "node_id": "…", "status": "ok", "token": "…"}
// 其余消息(heartbeat / doc_update / doc_request / doc_response)不变
```

## 8. 节点同步协议 🆕(hash-first)

```jsonc
// PUT /api/nodes/{id}/documents
{
  "documents": [
    {"path": "a.md", "title": "A", "hash": "…", "size": 1, "content": "…"}, // 新增/变更:带全文
    {"path": "b.md", "hash": "…"}                                           // 未变:只报 hash
  ],
  "deletions": ["c.md"]
}
// 响应:{"created": n, "updated": n, "deleted": n, "rejected": [{"path":"…","reason":"…"}]}
```
