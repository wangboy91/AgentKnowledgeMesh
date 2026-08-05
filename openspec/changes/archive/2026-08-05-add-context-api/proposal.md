## Why

AI Agent（如 Claude Code、Codex）无法直接查询 AgentVault 知识库。需要一个统一的 Context API，让 Agent 能够根据用户问题检索相关知识并注入到 prompt 中。

## What Changes

- 新增 `GET /api/context?q=xxx` 端点，返回与查询相关的文档
- 返回格式适配 Agent prompt 注入（包含标题、内容、来源）
- 支持限制返回文档数量（`limit` 参数）
- 支持指定节点过滤（`node_id` 参数）

## Capabilities

### New Capabilities

- `context-api`: Agent Context API，让 AI Agent 查询知识库获取相关上下文

### Modified Capabilities

- `api`: 在现有 API 规格中添加 context 端点

## Impact

- 新增文件：`server/api/context.py`
- 修改文件：`server/api/router.py`（注册路由）
- 前端：无需修改（API only）
- Node：无需修改（Hub 端处理）
