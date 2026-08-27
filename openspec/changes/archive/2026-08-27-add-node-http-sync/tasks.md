## 1. Hub 端：节点令牌下发

- [x] 1.1 在 `src/server/app/services/websocket.py` 的 `handle_register` 返回的 `register_ack` 中增加 `token` 字段（新节点由模型 `default` 生成并持久化，已存在节点复用其令牌），验证注册后 Hub 返回含 `token` 的 `register_ack`

## 2. Hub 端：节点文档入库端点

- [x] 2.1 在 `src/server/app/api/nodes.py` 新增 `PUT /api/nodes/{node_id}/documents`：校验 `Authorization: Bearer <token>`（不一致 401、节点不存在 404），按 `(node_id, path)` 作用域增量 upsert/delete（哈希不同更新、列表缺失删除），返回 `{"created","updated","deleted"}`，验证端点单测覆盖新增/更新/删除/作用域隔离/401/404
- [x] 2.2 确保端点调用不触及 `local` 或其他节点的文档（作用域严格限定为路径中的 `node_id`），验证单测断言隔离行为

## 3. Node 端：HTTP 文档上传

- [x] 3.1 在 `src/node/app/transport.py` 解析 `register_ack` 并保存 `self.token` 到内存，验证注册后 Node 持有令牌
- [x] 3.2 在 `src/node/app/sync.py` 实现 `sync_documents()`：扫描（`akm_shared.scanner`）→ 以 `httpx` `PUT {hub_api_url}/nodes/{node_id}/documents`（携带 `Authorization: Bearer <token>`）上传文档列表 → 记录返回统计；鉴权失败仅记日志不中断连接，验证连接本地 Hub 冒烟：初始连接后文档入库并打印统计

## 4. 测试与文档

- [x] 4.1 为端点鉴权/作用域隔离与 Node 上传路径补充 pytest 覆盖，验证 `cd src/server && uv run pytest -q` 通过
- [x] 4.2 更新 `README.md` API 表格新增 `PUT /api/nodes/:id/documents` 一行，验证文档与实现一致
