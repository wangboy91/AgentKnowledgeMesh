# Tasks: add-node-mcp-proxy

## 1. 代理骨架

- [ ] 1.1 node `pyproject.toml` 增加 `mcp` 依赖并 `uv sync`;`__main__.py` 增加 `--mcp` 分支(不启动同步循环);无凭证时输出 login 引导并退出(退出码 1),手测验证
- [ ] 1.2 新增 `app/mcp_proxy.py`:stdio MCP server 注册三个工具(`search_documents`/`get_document`/`list_documents`),参数签名与 Hub MCP 一致;`npx @modelcontextprotocol/inspector` 连接可见工具清单

## 2. Hub 转调与错误处理

- [ ] 2.1 实现转调:search → `GET /api/search`、get → `GET /api/documents/{id}`、list → `GET /api/documents`;统一 10s 超时;返回格式与 Hub MCP 工具对齐(单测:格式化函数覆盖命中/空结果/不存在)
- [ ] 2.2 错误映射单测:连接失败 → "无法连接 Hub"、401 → "凭证已失效请重新 login"、超时 → 明确提示;进程不崩溃(MCP 会话存活)
- [ ] 2.3 与 Hub 工具输出一致性:同一查询分别经 Hub SSE 与节点代理调用,人工比对三工具输出格式一致

## 3. 端到端验证

- [ ] 3.1 完整链路手测(Hub + 已 login 节点):Claude Code 配置 `akm-node --mcp` → `search_documents` 命中节点同步的文档 → `get_document` 取回全文;禁用节点 token 后工具返回"凭证已失效"
- [ ] 3.2 回归:`uv run pytest`(node + server)全绿;节点同步功能不受 `--mcp` 分支影响(普通模式冒烟)

## 4. 收尾

- [ ] 4.1 README「AI 工具接入」与 `docs/technical-design.md` §9 若有出入则同步;MCP Inspector 截图/命令行记录归档到任务报告
