# document-persistence · 任务清单

## 1. 数据模型与迁移

- [x] 1.1 `Document` 新增 `origin` 列(`String(8)`,默认 `file`,`index=True`),并在 `to_dict` 输出该字段;验证:`test_document_origin.py::test_create_document_marks_agent` 断言返回记录含 `origin` → 通过
- [x] 1.2 `db.py::_COLUMN_MIGRATIONS` 为 `sqlite` 与 `postgresql` 各登记一条 `documents.origin` 补列 DDL(`NOT NULL DEFAULT 'file'`);验证:`test_document_origin.py::test_migrate_adds_origin_column_defaulting_to_file`(建无 origin 列的旧表 + 插旧行 → 跑 `_migrate_columns()` → 列存在且旧行为 `file`)→ 通过

## 2. 写入口径转 agent

- [x] 2.1 `document_writer.create_document` 置 `origin="agent"`;验证:`test_create_document_marks_agent`;REST 与 MCP 两条通道在端到端验证中均产出 `origin=agent`(见 §6)
- [x] 2.2 `document_writer.update_document` 置 `doc.origin = "agent"`;验证:`test_update_document_switches_to_agent`(file → agent)与 `test_update_document_keeps_agent_origin`(agent → agent,转换单向)

## 3. Hub 扫描作用域收窄

- [x] 3.1 `indexer.sync_documents` 的 `existing` 构造收窄为 `node_id="local" AND origin="file"`,统计新增 `skipped`;验证:`test_hub_scan_keeps_agent_doc_missing_from_disk`、`test_hub_scan_does_not_overwrite_agent_doc`、`test_hub_scan_agent_and_file_coexist`
- [x] 3.2 单独查询 `local` 且 `agent` 的路径集合,扫描命中同路径时跳过并计入 `skipped`(避免 `(node_id, path)` 唯一约束冲突);验证:`test_hub_scan_does_not_overwrite_agent_doc` + 端到端 A3/A4(磁盘写入同路径文件 → `skipped=1`、库中内容不变、无异常)
- [x] 3.3 回归:`origin="file"` 的 local 文档仍按 hash 更新、仍按"消失即删"清理;验证:`test_hub_scan_still_deletes_file_doc`、`test_hub_scan_still_updates_file_doc` + 既有 `test_indexer_scope.py` 全绿

## 4. 节点入库对 agent 来源免疫

- [x] 4.1 `_sync_node_documents` 在取到 `old_doc` 后,若 `old_doc.origin == "agent"` 则跳过该条目并计入 `skipped`(含 path 与原因),**不计入 `rejected`**;验证:`test_node_sync_skips_agent_doc_full_content`、`test_node_sync_agent_doc_hash_only_not_rejected`
- [x] 4.2 删除推导(`deletions` 与 `implicit_delete`)过滤掉 `agent` 来源路径;验证:`test_node_sync_deletions_keep_agent_doc`、`test_node_sync_implicit_delete_keeps_agent_doc`
- [x] 4.3 响应新增 `skipped` 字段,`PUT /api/nodes/{node_id}/documents` 返回 `{created, updated, deleted, rejected, skipped}`;验证:`test_node_sync.py` 既有 15 处响应断言已同步更新,全文件用例全绿

## 5. 验证基线

- [x] 5.1 `cd src/server && .venv/Scripts/python.exe -m pytest --basetemp=<唯一临时目录>` → **203 passed**(基线 188 + 本次新增 15)
- [x] 5.2 `cd src/web && npm test`(6 文件 42 用例)+ `npm run build`(tsc + vite 成功)通过(本次不改前端,确认无连带影响)
- [x] 5.3 `/c/nvm4w/nodejs/openspec validate 2026-09-30-fix-document-persistence --strict` → 通过

## 6. 端到端实测(隔离 Hub + 真实节点)

环境:隔离 Hub(SQLite,`:8899`,`hub_knowledge`)+ 隔离 Node(`AKM_NODE_ENV_FILE` 与
`AKM_NODE_STATE_DIR` 均指向临时目录,`WATCH_RECONCILE_SECONDS=10`)。
驱动脚本:`.workbuddy-ai/tmp/e2e/verify_origin.py`(21 项)与 `verify_mcp_origin.py`(8 项)。

- [x] 6.1 问题 1 修复:
  - **local 分支**:`local.md` 扫描入库(`origin=file`)→ Hub 编辑 → 再扫描 → 内容仍为编辑版本、`updated=0`、`origin=agent`
  - **节点分支**:`note.md` 由节点推送(`origin=file`)→ Hub 编辑 → 节点凭证推 hash-only 不一致条目 → `rejected=[]` 且 `skipped=[{path,reason:"agent origin"}]`;推全文 → `updated=0` 且内容不变;再对真实节点发 `sync_request` 触发全量对账 → 40 秒内内容始终保持编辑版本
- [x] 6.2 问题 2 修复:经 REST `POST /api/documents`、Hub stdio MCP `create_document`、节点代理 MCP `create_document` 三条通道新建的文档均为 `origin=agent`,调用 `POST /api/documents/scan` 后**全部仍存在且内容未变**;磁盘出现同路径文件时计入 `skipped` 且不夺回内容
- [x] 6.3 回归:`file` 来源文档改磁盘文件 → 内容按预期更新(`updated=1`);删除磁盘文件 → Hub 文档被删除(`deleted=1`);节点侧新增/修改/删除文件仍正常同步(`origin` 保持 `file`)

## 7. 文档与收尾

- [x] 7.1 `docs/known-issues.md` 问题 1 / 问题 2 状态由「待决」更新为「已修」并注明变更名与修复方式,索引表同步;问题 3 保持「待决」
- [x] 7.2 `docs/api-reference.md` 同步:§2 新增 `origin` 语义说明并标注 scan / POST / PUT 的行为变化;§8 节点同步协议响应补 `skipped` 字段与「agent 来源免疫」条目
- [x] 7.3 行为变化同步用户视角与工程视角文档:`README.md`(智能体写回段落补「写回是持久的」)、`docs/agent-write-back-design.md`(修正"磁盘文件随后收敛"的过时表述)
- [x] 7.4 红线自查(workflow.md §3):无业务领域绑定;未触碰仓外仓库与参考仓;对外契约变更(文档对象 `origin`、节点上传与扫描响应 `skipped`)均为向后兼容新增并已同步 `docs/api-reference.md`;未混入私有部署配置

## 8. 遗留(不在本次范围)

- [x] 8.1 **归档**:`openspec archive 2026-09-30-fix-document-persistence -y` 已执行(2026-09-30)——delta specs 合入 `openspec/specs/`:`document-management` / `knowledge-indexing` / `mcp-integration` / `multi-node-sync` 共 7 个 requirement 更新;归档后 `validate --all --strict` 14/14 通过;基线场景逐个核对无丢失
- [ ] 8.2 `agent` 来源文档无删除入口(REST / MCP / Web 均无),需要独立的删除能力变更
- [ ] 8.3 版本机制(known-issues 问题 3):无版本号 / ETag / 乐观锁,两个编辑者之间仍为最后写入者胜
- [ ] 8.4 「从文件重新同步」回退操作(把 `agent` 文档转回 `file`、让磁盘夺回权威)
