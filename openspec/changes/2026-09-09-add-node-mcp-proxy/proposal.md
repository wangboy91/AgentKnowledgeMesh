# Proposal: add-node-mcp-proxy

## Why

智能体接入知识库需逐个配置 Hub 地址与凭证(API Token),且凭证散落在各机器的智能体配置中;而每台有智能体的机器本来就会安装 `akm-node`。节点应成为智能体的**本地 MCP 入口**:智能体只配一条本地命令,Hub 地址与凭证永远只存在节点本机。

## What Changes

- 新增节点本地 MCP 代理模式:`uv run akm-node --mcp` 以 stdio 提供与 Hub 完全同名同参的三个工具(`search_documents` / `get_document` / `list_documents`)
- 代理内部转调 Hub HTTP API(复用节点已有 httpx 与节点凭证):search → `/api/search`(可扩展 `mode=semantic`)、get → `/api/documents/{id}`、list → `/api/documents`
- 节点凭证(`AKM_NODE_ID` / `AKM_NODE_TOKEN`,由 `akm-node login` 写入)作为对 Hub 的只读凭证使用;Hub 不可达时工具返回明确错误信息
- 未登录(无本地凭证)时启动 MCP 模式给出"请先执行 akm-node login"引导
- 节点**不做**本地向量检索:检索质量由 Hub 保证,节点只做就近代理;离线降级(本地现扫关键词)列为 V1.0 备选
- Hub SSE / stdio 形态保留不变(SSE 鉴权由 add-account-auth 变更覆盖)

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `mcp-integration`: 传输形态新增"节点本地 stdio 代理",工具集与 Hub 一致

## Impact

- **node**:新增 `mcp_proxy.py`(stdio server,`mcp` Python SDK);`__main__.py` 增加 `--mcp` 分支;pyproject 增加 `mcp` 依赖
- **server**:无新端点(依赖 add-account-auth 的 node token 只读授权)
- **web**:无
- **文档**:README / docs 的智能体接入推荐方式改为节点本地代理
- **依赖**:node 包新增 `mcp`(与 server 同源 SDK)
