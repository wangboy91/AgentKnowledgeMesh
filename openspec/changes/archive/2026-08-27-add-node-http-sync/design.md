## Context

见 proposal.md 的 Why。Node 端 `sync_documents()` 目前只打印扫描结果（TODO 未实现），Hub 没有接受节点文档入库的端点，`nodes.token` 字段存在但从未被校验。本变更依赖 `restructure-node-and-rebrand` 先落地（`akm-node` 包结构、`akm-shared` 扫描器、`AKM_` 前缀），因此下述路径以重构后的结构为准。

## Goals / Non-Goals

**Goals:**
- Node 扫描结果真正入库 Hub，形成完整数据通路。
- 文档入库按 `(node_id, path)` 作用域增量同步，节点对自己的文档负责。
- `nodes.token` 落地为真实鉴权。

**Non-Goals:**
- 不做实时文件监听（`doc_update` 增量通知仍是既有 WS 消息语义，不在本次实现自动触发）。
- 不做 Hub→Node 的文档回写或冲突合并。
- 不做多节点间文档去重/合并（每个节点独立命名空间）。

## Decisions

### 1. 传输通道：HTTP（`httpx`）而非 WebSocket
Node 已有 `hub_api_url` 与 `httpx` 依赖；文档列表是批量、非实时、可幂等的数据，适合 HTTP 而非复用 WS 消息流。WS 继续负责控制面（注册/心跳/`sync_request`/`doc_request`），数据面走 HTTP。备选：扩展现有 `doc_response` WS 消息流式上传——否决，需改 Hub 的 WS 处理与逐条状态管理，复杂度高、收益低。

### 2. Hub 端点：`PUT /api/nodes/{node_id}/documents`
接收体 `{"documents": [{"path","title","hash","size","content"}]}`，令牌鉴权（`Authorization: Bearer <token>`）。处理语义与 `POST /api/documents/scan` 的增量逻辑一致，但作用域限定为该 `node_id`：
- 列表内路径：按 `(node_id, path)` 查重，哈希不同则更新（标题/哈希/大小/内容），否则不动。
- 该节点既有但列表缺失的路径：删除。
- 返回 `{"created", "updated", "deleted"}`。

`PUT`（幂等全量替换语义）比 `POST` 更贴合"节点上报其完整文档集合"的含义。备选：`POST /api/nodes/{node_id}/sync-documents`——否决，`sync` 已用于触发信号端点（`POST /api/nodes/{id}/sync`），语义易混淆。

### 3. 令牌：注册下发、内存持有、端点强制校验
- Hub：`register` 时若该节点无令牌则生成（`secrets.token_urlsafe(32)`）并持久化到 `nodes.token`，`register_ack` 增加 `token` 字段返回；已有令牌则复用（满足 spec 的"稳定复用"场景）。
- Node：`transport.py` 解析 `register_ack` 保存 `self.token`（仅内存，重启后由重新注册再获得）；`sync.py` 上传时携带 `Authorization: Bearer <token>`。
- Hub 校验：端点读取令牌后与 `nodes.token` 比对，不一致返回 401；`node_id` 不存在返回 404。

备选：Node 自生成令牌并在注册时声明——否决，令牌应由 Hub 权威签发，避免节点身份冒用。

### 4. 端点鉴权与节点文档查询的一致性
现有 `GET /api/nodes/{node_id}/documents` 为免鉴权的管理/浏览接口，本次不为其加鉴权（避免波及前端节点管理界面）。新写入端点单独强制令牌校验——写入比读取更需要保护。备选：全节点 API 统一鉴权——否决，超出本次范围且需前端配套改造。

### 5. 同步触发点复用现有信号
`runner.py` 已在线程里做初始 `sync_documents()`，`transport.py` 收到 `sync_request` 时也调用。实现仅替换 `sync_documents()` 内部逻辑（扫描 → HTTP 上传 → 记录统计），不改触发编排。上传失败（含 401）仅记录日志、不中断 WS 连接，等待下次触发重试。

## Risks / Trade-offs

- [鉴权端点引入后，未带令牌的旧 Node 版本上传会 401] → 本变更与 Node 实现同步落地；`register_ack` 新增 `token` 字段为向后兼容（旧 Node 忽略新字段不报错）。
- [全量替换语义下，若节点漏报某文档会误删] → Node 每次全量扫描再上报（现有逻辑已是全量扫描），漏报风险来自扫描本身而非协议；删除仅限该节点作用域。
- [Hub 单点令牌存于 DB，无过期/轮换机制] → 属未来安全增强，本次仅落地最小可用鉴权；在 Open Questions 记录。

## Migration Plan

1. 先落 Hub 侧：`register_ack` 返回令牌 + 新端点 + 令牌校验（Node 未实现时端点暂无人调用，安全）。
2. 再落 Node 侧：`sync_documents()` 实现 HTTP 上传。
3. 验证：单元测试（端点鉴权/作用域隔离/增量统计）+ 手动连本地 Hub 冒烟（注册→初始上传→`POST /api/nodes/{id}/sync` 触发二次上传）。
4. 回滚：`git revert`；已入库的节点文档随节点删除或再次同步自然收敛。

## Open Questions

- 令牌是否需要过期/轮换、是否需要在 `GET /api/nodes` 中隐藏——属后续安全硬化，不影响本次 spec/结构/任务，可延后决定。
