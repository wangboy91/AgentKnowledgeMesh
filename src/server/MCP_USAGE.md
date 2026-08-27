# MCP Server 使用指南

## 概述

AgentKnowledgeMesh 提供 MCP (Model Context Protocol) Server，让 AI 工具可以直接访问知识库。

## 启动方式

### 1. HTTP 模式（推荐）

启动服务器后，MCP 端点自动可用：

```bash
cd src/server
uv run agentvault
```

MCP 端点：
- SSE: `http://localhost:8000/api/mcp/sse`
- Messages: `http://localhost:8000/api/mcp/messages`

### 2. Stdio 模式

```bash
cd src/server
uv run agentvault --mcp
```

## 配置 Claude Code

在项目根目录创建 `.claude/mcp.json`：

```json
{
  "mcpServers": {
    "agentknowledge": {
      "url": "http://localhost:8000/api/mcp/sse"
    }
  }
}
```

或使用 stdio 模式：

```json
{
  "mcpServers": {
    "agentknowledge": {
      "command": "uv",
      "args": ["run", "agentvault", "--mcp"],
      "cwd": "src/server"
    }
  }
}
```

## 可用工具

### search_documents

搜索知识库中的文档。

**参数**：
- `query` (string, 必需): 搜索关键词
- `limit` (integer, 可选): 返回结果数量，默认 5

**示例**：
```
搜索关于"项目架构"的文档
```

### get_document

获取指定文档的完整内容。

**参数**：
- `document_id` (integer, 必需): 文档 ID

**示例**：
```
获取文档 ID 42 的内容
```

### list_documents

列出知识库中的文档。

**参数**：
- `node_id` (string, 可选): 节点 ID
- `limit` (integer, 可选): 返回数量，默认 20

**示例**：
```
列出最近的 10 个文档
```

## 测试 MCP 连接

使用 MCP Inspector 测试：

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/sse
```

## Claude Desktop 配置

在 `~/Library/Application Support/Claude/claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "agentknowledge": {
      "url": "http://localhost:8000/api/mcp/sse"
    }
  }
}
```

## 故障排除

### 连接失败

1. 确认服务器已启动
2. 检查端口是否被占用
3. 查看服务器日志

### 工具调用错误

1. 检查数据库是否有数据
2. 确认文档 ID 存在
3. 查看错误信息
