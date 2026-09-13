# Tasks: add-node-mcp-proxy

## 1. 代理骨架

- [x] 1.1 node `pyproject.toml` 增加 `mcp` 依赖并 `uv sync`;`__main__.py` 增加 `--mcp` 分支(不启动同步循环);无凭证时输出 login 引导并退出(退出码 1),手测验证
- [x] 1.2 新增 `app/mcp_proxy.py`:stdio MCP server 注册三个工具(`search_documents`/`get_document`/`list_documents`),参数签名与 Hub MCP 一致;`npx @modelcontextprotocol/inspector` 连接可见工具清单

## 2. Hub 转调与错误处理

- [x] 2.1 实现转调:search → `GET /api/search`、get → `GET /api/documents/{id}`、list → `GET /api/documents`;统一 10s 超时;返回格式与 Hub MCP 工具对齐(单测:格式化函数覆盖命中/空结果/不存在)
- [x] 2.2 错误映射单测:连接失败 → "无法连接 Hub"、401 → "凭证已失效请重新 login"、超时 → 明确提示;进程不崩溃(MCP 会话存活)
- [x] 2.3 与 Hub 工具输出一致性:同一查询分别经 Hub SSE 与节点代理调用,人工比对三工具输出格式一致

## 3. 端到端验证

- [x] 3.1 完整链路手测(Hub + 已 login 节点):Claude Code 配置 `akm-node --mcp` → `search_documents` 命中节点同步的文档 → `get_document` 取回全文;禁用节点 token 后工具返回"凭证已失效"
- [x] 3.2 回归:`uv run pytest`(node + server)全绿;节点同步功能不受 `--mcp` 分支影响(普通模式冒烟)

## 4. 收尾

- [x] 4.1 README「AI 工具接入」与 `docs/technical-design.md` §9 若有出入则同步;MCP Inspector 截图/命令行记录归档到任务报告

## 2.5 语义检索(mode=semantic,用户追加)

- [x] 2.5.1 `search_documents` 增加 `mode` 参数(`keyword`/`semantic`,默认 keyword);代理 semantic 转发 `GET /api/rag/search`(dense⊕sparse 加权 RRF 混合检索);Hub mcp_server 同步支持,三形态签名与输出一致
- [x] 2.5.2 语义结果格式化 `format_semantic_search`(含分数与命中分块,入 `akm_shared`);单测:命中/空/error 字段/路由;Hub+代理 E2E 降级一致性验证

## 验证记录(2026-09-11)

- **工具清单**:`npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/sse`(Hub SSE);节点本地代理等价用法为拉起 `uv run akm-node --mcp`。E2E 以 MCP SDK `stdio_client` 直连子进程完成等价验证:`list_tools` 返回 `search_documents` / `get_document` / `list_documents`,**参数签名与 Hub MCP 逐字段一致**。
- **一致性(任务 2.3)**:同一 Hub(SQLite 测试库,3 篇文档)下,经 `akm-node --mcp` 与 `akm-hub --mcp` 分别调用三工具,`search_documents` / `get_document` / `list_documents` 输出**字符级完全一致**。
- **全链路(任务 3.1)**:真实 DocumentSync 同步 3 篇 → `search_documents` 命中(mcpmarker42,2 篇)→ `get_document` 取回全文 → `list_documents` 列出 3 篇;禁用节点后工具返回 "节点凭证已失效,请重新执行 akm-node login",进程不退出。
- **回归(任务 3.2)**:node 31 passed, server 61 passed。
- **语义检索(2.5)**:`search_documents` 增加 `mode=semantic`(代理转发 `GET /api/rag/search` 混合检索,Hub 端直调 `search_hybrid`);隔离 Hub(无向量)下代理与 Hub stdio 均降级返回"语义检索失败"错误文本,进程不崩;签名(含 mode schema)两端逐字段一致。真实语义命中由 Hub 混合检索能力保证(开发库 PG + 已向量化文档),可用下述命令验证:`curl.exe -G "$env:.../rag/search" --data-urlencode "q=查询" -H "Authorization: Bearer <node_token>"`。
