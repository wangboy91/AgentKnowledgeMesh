## Context

AgentVault 已有搜索 API（`GET /api/search?q=xxx`），返回文档列表但不含内容。Agent 需要一个专门的端点，返回包含完整内容的文档，以便注入到 prompt 中。

## Goals / Non-Goals

**Goals:**
- 提供 `/api/context` 端点，返回与查询相关的文档（含内容）
- 返回格式便于 Agent 直接使用（标题 + 内容 + 来源）
- 支持 `limit` 和 `node_id` 参数

**Non-Goals:**
- 不实现向量搜索（V1.0）
- 不实现 MCP Server（V0.3 后续）
- 不修改前端

## Decisions

### 1. 复用现有搜索逻辑

**决定**: 复用 `api/search.py` 的 LIKE 搜索逻辑

**理由**: V0.1 的关键词搜索已可用，Context API 本质上是"搜索 + 返回内容"

**替代方案**: 实现新的搜索引擎 → 过度设计

### 2. 返回格式

**决定**: 返回结构化 JSON，包含 `documents` 数组，每个文档有 `title`、`content`、`path`、`node_id`

**理由**: Agent 可以直接解析并构造 prompt

**替代方案**: 返回纯文本 → 灵活性不足

### 3. 端点路径

**决定**: `GET /api/context?q=xxx&limit=5&node_id=local`

**理由**: 与设计文档一致，语义清晰

## Risks / Trade-offs

- [性能] 大量文档内容返回可能较慢 → 限制 `limit` 默认值为 5
- [安全] 无认证，任何人可访问 → V0.3 后续添加 token 认证

## Migration Plan

无需迁移，纯新增功能。

## Open Questions

无
