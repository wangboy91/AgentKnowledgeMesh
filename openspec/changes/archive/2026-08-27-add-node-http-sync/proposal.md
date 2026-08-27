## Why

Node 端 `sync_documents()` 目前只扫描并打印文档列表（代码中留有 `# TODO: 实现 HTTP 同步`），Node 扫描到的本地 Markdown 从未真正入库到 Hub，多节点知识共享只停留在"远程读取"层面。补齐这条数据通路，才能让 Node 成为 Hub 的真正数据来源，也为后续 `doc_update` 增量通知落地提供基础。

## What Changes

- **Node 文档上传**：`sync_documents()` 改为将扫描结果通过 HTTP 推送到 Hub，触发时机为初始连接成功后与收到 `sync_request` 时（与现有触发点一致）。
- **Hub 节点文档入库端点**：新增 `PUT /api/nodes/{node_id}/documents`，按 `(node_id, path)` 作用域增量 upsert（按 SHA256 哈希判定新增/更新/删除），返回同步统计；仅影响该节点名下文档，绝不触及 `local` 或其他节点的文档。
- **节点令牌鉴权**：Hub 在 `register_ack` 中下发（或复用）节点令牌，Node 持有令牌并在上传时以 `Authorization: Bearer <token>` 携带；Hub 校验令牌，使此前从未被强制执行的 `nodes.token` 首次落地为真实鉴权。

## Capabilities

### New Capabilities

（无全新能力——扩展现有的多节点同步能力。）

### Modified Capabilities

- `multi-node-sync`: 新增节点文档上传、Hub 节点文档入库、节点令牌下发/鉴权三条需求。

## Impact

- **代码**：`src/node/app/sync.py`（实现 HTTP 上传，替换 TODO）、`src/server/app/api/nodes.py`（新增端点）、`src/server/app/services/websocket.py`（`register_ack` 返回令牌）、`src/server/app/models/`（如节点令牌字段缺失则补齐）。
- **配置**：Node 复用现有 `hub_api_url` 与 `httpx` 依赖，无新增环境变量。
- **依赖**：`restructure-node-and-rebrand` 落地后本变更才可实施（依赖 `akm-node` 包结构与 `akm-shared` 扫描器）。
- **协议**：WebSocket `register_ack` 消息新增 `token` 字段；`doc_update`/`doc_response` 既有消息语义不变。
