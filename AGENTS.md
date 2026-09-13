# AGENTS.md · 工程规约地图

> 在本仓工作的 AI 会话与开发者从这里出发。团队章程(身份与铁律)见 `CLAUDE.md`;用户视角的项目说明见 `README.md`。

## 1. 项目一句话

AgentKnowledgeMesh 是一个**独立项目**:面向 AI Agent 时代的分布式知识库(Hub + Node)—— 多机 Markdown 汇聚、关键词⊕语义混合检索、MCP / Context API 接入。可独立部署为团队/企业内网知识库,也可作为知识组件被上层应用集成。

## 2. 规约地图

| 想了解 / 要做的事 | 去哪里 |
| --- | --- |
| 产品定位、角色权限、功能地图、迭代计划 | [docs/product-overview.md](docs/product-overview.md) |
| 当前批次的技术设计(账号鉴权/CLI 接入/同步/RAG 模式/i18n/树形) | [docs/technical-design.md](docs/technical-design.md) |
| 全部 API 端点 | [docs/api-reference.md](docs/api-reference.md) |
| **UI 规范**(布局/主题/i18n/交互) | [docs/conventions/ui.md](docs/conventions/ui.md) |
| **流程规范**(openspec 生命周期/验证基线/红线自查) | [docs/conventions/workflow.md](docs/conventions/workflow.md) |
| **文件规范**(目录/命名/职责边界) | [docs/conventions/files.md](docs/conventions/files.md) |
| 正式规范(能力 spec) | `openspec/specs/` |
| 进行中/历史变更 | `openspec/changes/` |

## 3. 仓库结构

```
src/
├── server/   # Hub 后端(FastAPI + SQLAlchemy async;uv run akm-hub [--mcp])
│   └── app/  # main / config / db / models / services(scanner·indexer·websocket·rag·converters·mcp_server)/ api
├── node/     # Node 客户端(uv run akm-node):transport / sync / runner / config
├── web/      # 前端(React18+Vite+TS):components / pages / api/client.ts / ThemeContext
└── shared/   # akm_shared:统一 Markdown 扫描器(server 与 node 共用)
```

细节与职责边界见 [docs/conventions/files.md](docs/conventions/files.md)。

## 4. 开发命令

```bash
# Hub 后端
cd src/server && uv sync && uv run akm-hub          # :8000;--mcp 为 stdio 模式
# 前端
cd src/web && npm install && npm run dev            # :5173,代理 /api → :8000
# 节点
cd src/node && uv sync && uv run akm-node
# 测试与构建
cd src/server && uv run pytest
cd src/web && npm run build
# 检索评测(可选)
cd src/server && uv run python eval/run_eval.py
```

配置:复制 `src/server/.env.example` → `.env` 按需修改(数据库/嵌入模型/知识库目录;全变量带 `AKM_` 前缀,清单见 `.env.example` 注释)。

## 5. 常用验证目标

- 扫描:`POST /api/documents/scan` 后查 `/api/documents`
- 搜索:`GET /api/search?q=`(关键词)、`GET /api/rag/search?q=`(语义/混合)
- 多节点:Hub + Node 同机起,观察 WS 注册 → 心跳 → `PUT /nodes/{id}/documents`
- 前端:明暗两主题各过一遍;文案不得硬编码(见 ui.md)
- 数据库:SQLite 与 PostgreSQL 双路径

## 6. 环境事实(易踩坑)

- Windows 下后台/管道运行必须 UTF-8 输出(已在入口统一 reconfigure;新增 print 保持编码安全)
- 向量库 = PostgreSQL + pgvector(主库为 SQLite 时可独立配置,见 `.env.example` §4)
- `src/server/.env` 属本机私有配置,不入库;勿把其中密钥写入任何文档/日志
