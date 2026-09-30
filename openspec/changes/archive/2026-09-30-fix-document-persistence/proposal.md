# fix-document-persistence

## Why

`docs/known-issues.md` 记录的问题 1 与问题 2 是**同一个根因的两种表现**:文档没有"来源"标记,
系统无法区分「这篇文档的内容由磁盘文件派生」与「这篇文档的内容由 Hub/智能体写入」。
于是两处"文件是权威"的推导会无差别地打回智能体的写入:

- **问题 1(编辑是暂态的)**:在 Web 或经 MCP 编辑一篇**有对应磁盘文件**的文档,当时能看到新内容;
  节点下一轮同步(默认 300 秒定时对账,或文件变更触发的监听同步)会把内容覆盖回磁盘版本。
  机制:`_sync_node_documents` 对 hash-only 条目在 `old_doc.hash != doc.hash` 时计入 `rejected`
  → 节点把该路径移出快照 → 下轮带全文重传 → 覆盖。`local` 文档同理:Hub 扫描
  (`indexer.sync_documents`)按 hash 不一致用磁盘内容覆盖 DB 内容。
- **问题 2(新建的文档会被删)**:`POST /api/documents` 与 MCP `create_document` 只写 DB、
  不落磁盘;`indexer.sync_documents` 的删除推导是 `set(existing) - scanned_paths`
  (local 作用域内"库里有、磁盘上没有 → 删"),会把智能体新建的文档删掉。

**影响面**:批次 3「智能体写回」在多机协作场景下不成立——智能体写的东西会自己消失。
用户场景(云端 Hub + 局域网多节点,两侧智能体都要能读写)直接卡在这里:
检索链路完整可用,写入链路没有持久性保证。

**期望行为**:智能体经 Hub 写入的文档,内容以 Hub 为准,不再被磁盘文件事件覆盖或删除;
磁盘派生且未被改写的文档,继续由文件扫描与节点同步正常维护。

## What Changes

- **文档数据模型新增 `origin` 字段**(`file` / `agent`),标识内容的权威来源:
  - `file`(默认):内容由文件扫描派生(Hub 本机目录扫描、节点磁盘扫描上传),磁盘是权威;
  - `agent`:内容由 Hub/智能体写入(REST `POST /api/documents`、`PUT /api/documents/{id}`、
    MCP `create_document` / `update_document`),**无对应磁盘文件**,Hub 库是权威。
- **写入口径把文档标记为 `agent`**:`document_writer.create_document` 一律置 `agent`;
  `update_document` 把被改写文档置为 `agent`(内容已脱离磁盘,不再接受文件事件覆盖)。
  REST 与 MCP 共用该单源,故两侧行为天然一致。
- **Hub 扫描只管理 `file` 来源的 `local` 文档**:`indexer.sync_documents` 的增量与删除推导
  只在 `origin=file` 的集合内进行;`agent` 来源的文档既不覆盖也不删除。扫描命中同路径时
  跳过并计入新增的 `skipped` 统计(避免与既有 `agent` 文档争 `(node_id, path)` 唯一约束)。
- **节点入库不覆盖 `agent` 来源的文档**:`_sync_node_documents` 遇到 `old_doc.origin == "agent"`
  的条目时跳过——既不覆盖、也不计入 `rejected`(计入 rejected 会让节点把该路径移出快照、
  每轮带全文重传,形成无意义的重传循环)。该情况计入响应新增的 `skipped` 列表。
  `agent` 来源的文档同样不参与 `deletions` / 隐式缺失的删除推导。
- **`origin` 暴露在文档响应中**(`to_dict`),供前端与调用方判断文档是否受文件事件影响。

**刻意的语义选择**:`agent` 来源的文档对**一切**文件来源事件免疫(不覆盖、不删除),
包括节点显式上报的 `deletions`。理由是一句话可解释、可测:智能体写入的内容不会因磁盘变化消失。
代价是「磁盘文件删除后 Hub 文档仍保留」,且当前**没有文档删除入口**
(`/api/documents` 只有 GET/POST/PUT,Web 亦无删除按钮)——该缺口在本次范围外,见 design.md。

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `document-management`:Requirement「Document Creation」与「Document Update」新增"写入即标记为 `agent` 来源"的行为约定
- `knowledge-indexing`:Requirement「Incremental Index Sync」限定增量与删除推导仅作用于 `file` 来源文档;
  Requirement「Document Data Model」新增 `origin` 字段
- `multi-node-sync`:Requirement「Hub Node Document Ingestion」新增"不覆盖/不删除 `agent` 来源文档"
  与响应 `skipped` 统计
- `mcp-integration`:Requirement「Create Document Tool」与「Update Document Tool」明确写回的文档为 `agent` 来源

## Impact

- `src/server/app/models/document.py`:新增 `origin` 列与 `to_dict` 字段
- `src/server/app/db.py`:`_COLUMN_MIGRATIONS` 为 sqlite / postgres 补列(存量行默认 `file`)
- `src/server/app/services/document_writer.py`:`create_document` 置 `agent`;`update_document` 转 `agent`
- `src/server/app/services/indexer.py`:作用域收窄为 `origin=file`,新增 `skipped` 统计
- `src/server/app/api/nodes.py`:`_sync_node_documents` 跳过 `agent` 来源条目与删除,响应新增 `skipped`
- `src/server/tests/`:新增 `test_document_origin.py`
- `docs/api-reference.md`:文档响应新增 `origin`;节点上传响应新增 `skipped`;扫描响应新增 `skipped`
- `docs/known-issues.md`:问题 1 / 问题 2 状态更新
- **对外契约变更**:文档对象新增字段、节点上传与扫描响应新增字段,均为**向后兼容的新增**
  (节点端不读 `skipped`,旧节点行为不变;前端不读 `origin` 亦不受影响)
- **不改动** `src/node`、`src/web`、`src/shared`
- 与在制变更 `2026-09-30-fix-doc-viewer-header`(仅 `src/web/**`)无文件重叠

## Non-goals

- **不做版本机制**(问题 3:无版本号 / ETag / 乐观锁,最后写入者胜)。`agent` 与 `file` 之间的
  冲突靠"来源优先"消解,不做三方合并或人工选择保留哪一版。
- **不新增文档删除能力**(REST 端点 / MCP 工具 / Web 按钮)。`agent` 来源文档的清理入口缺失是
  已知缺口,另行决策。
- **不做编辑门控**:不禁止对 `file` 来源文档的编辑(编辑即转为 `agent`),前端亦不据此置灰。
- **不做"从文件重新同步"的显式回退操作**。
