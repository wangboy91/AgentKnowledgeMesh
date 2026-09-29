# Tasks: add-mcp-write-tools

> 状态:**实现、单测与端到端验证均已完成**。端到端经真实 Hub(SQLite,隔离实例)+ 真实 MCP stdio 代理执行。

## 1. 鉴权第三态(server)

- [x] 1.1 `require_auth` 增加 `node_write` 参数:节点凭证在 `node_write=True` 时放行(作用域由端点校验),否则维持既有 `allow_node` 语义与 403 文案
- [x] 1.2 单测:节点凭证在 `node_write=True` 端点放行;`node_write=False` 时仍 403;`min_role="admin"` 的非节点凭证行为不变

## 2. 写入口径单源(server)

- [x] 2.1 新增 `app/services/document_writer.py`:`create_document(session, *, node_id, path, content, title=None)` 与 `update_document(session, doc, content)`
- [x] 2.2 统一口径:标题提取(内容前 5 行 `# ` → 路径文件名)、SHA256、字节大小、`resolve_rag_status`、commit + refresh;`PathConflict` 异常表达冲突
- [x] 2.3 不做权限与作用域校验(端点职责);向量派发由调用方以 `doc.rag_status == "indexed"` 判定;向量载荷构造 `upsert_payload` 亦收敛到本模块(与 RAG 勾选流程共用)
- [x] 2.4 单测:标题提取三分支、hash/size 正确、`excluded` 粘性、冲突抛异常

## 3. REST 写端点(server)

- [x] 3.1 `POST /api/documents` 改 `require_auth("admin", node_write=True)`;归属 = 节点凭证取 `principal.node_id`,否则 `local`;唯一性改为 `(node_id, path)`
- [x] 3.2 `PUT /api/documents/{doc_id}` 改 `require_auth("admin", node_write=True)`;节点凭证且 `doc.node_id != principal.node_id` → 403
- [x] 3.3 两端点改为调用 2.1 的写入口径,向量派发条件改用 `doc.rag_status == "indexed"`(与现状等价)
- [x] 3.4 单测:节点创建归属本节点、跨节点更新 403、`(node_id, path)` 冲突 409、不同 node 同名路径 200、REST 写入字段与 MCP 一致

## 4. Hub MCP 写工具(server)

- [x] 4.1 `mcp_server.py` 新增 `create_document` / `update_document` 工具定义(含 `inputSchema` 与描述)
- [x] 4.2 `handle_call_tool` 增加分发;处理器调用 2.1 的写入口径,归属 `local`
- [x] 4.3 错误语义:冲突 → "路径已存在:<path>…请改用 update_document";不存在 → "文档 ID <id> 不存在。";缺参数 → "缺少参数: <名称>"
- [x] 4.4 单测:成功输出文案、冲突 / 不存在 / 缺参数文案、写入字段与 REST 一致

## 5. 节点代理写工具(node + shared)

- [x] 5.1 `akm_shared/mcp_formatting.py` 新增 `format_document_created` / `format_document_updated`
- [x] 5.2 `mcp_proxy.py` 新增 `_hub_write(method, path, json)` 与 `_safe_hub_write`(连接 / 超时 / 401 映射,与 `_safe_hub_get` 对称)
- [x] 5.3 `TOOLS` 与 `handle_call_tool` 增加两个写工具,转调 `POST /api/documents` 与 `PUT /api/documents/{id}`;请求体不含 `node_id`
- [x] 5.4 单测:转调方法 / 路径 / body 正确、不含 node_id、409 与 403 文案映射、401 文案、Hub 不可达不崩

## 6. 端到端验证(真实 Hub + 真实 MCP stdio 代理,已执行)

- [x] 6.1 经节点代理 `create_document` 写新文档 → Hub 文档树出现该节点下新条目(工具返回 `已创建文档 [105] 智能体写回`;树中 `notes/agent-note.md` 带 `id` 可见)
- [x] 6.2 `search_documents` 命中刚写入内容(关键词检索命中;`/api/search?q=内容已更新` 亦返回该文档)
- [x] 6.3 `update_document` 覆盖正文 → `updated_at` 更新、hash 变化(标题随之更新为"智能体写回 v2")
- [x] 6.4 A 节点凭证 update B 节点文档 → 越权文案(`无权修改该文档:不属于本节点。`)
- [x] 6.5 重复路径 `create_document` → 冲突文案(`路径已存在:notes/agent-note.md,请改用 update_document。`)
- [x] 6.6 另一台机器经其自身代理检索 → 命中该文档(闭环;`e2e-node-2` 代理检索到 `e2e-node-1` 写回的内容)
- [x] 6.7 附加:Hub stdio 形态(`akm-hub --mcp`)写回成功且归属 `local`;不同节点同名路径可共存(唯一性 `(node_id, path)`)

## 7. 收尾

- [x] 7.1 `src/server` pytest 187 passed(1 环境性 deselect)、`src/node` pytest 118 passed
- [x] 7.2 更新 `docs/api-reference.md`(节点凭证受限写权限、两写端点口径、MCP 工具表)、`README.md`(功能列表与写回说明)、`docs/conventions/files.md`(登记新设计文档)
- [x] 7.3 `openspec validate --strict` 通过;红线自查:无领域词汇、未触碰本仓外仓库、无私有部署配置混入交付路径
