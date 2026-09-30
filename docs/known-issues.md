# 已知问题记录

> **本文件只记录问题** —— 现象、触发条件、影响、代码证据、当前状态。
> 方案与变更计划**不在这里写**:讨论定案后另开 openspec 变更。
> 新增条目请同时更新下面的索引表。

## 索引

| # | 问题 | 涉及范围 | 状态 |
| --- | --- | --- | --- |
| 1 | Hub 端编辑对「文件来源」文档是暂态的,会被磁盘文件覆盖 | 文档写入 / 节点同步 / Hub 扫描 | 已修(2026-09-30-fix-document-persistence) |
| 2 | Hub 或智能体新建的文档会被 Hub 扫描删除 | 文档写入 / Hub 扫描 | 已修(2026-09-30-fix-document-persistence) |
| 3 | 无版本机制,写入一律「最后写入者胜」 | 文档写入 / 并发 | 待决 |

---

## 1. Hub 端编辑对「文件来源」文档是暂态的

**现象**:在 Web 上编辑一篇文档并保存,当时能看到新内容;过一段时间再打开,内容回到编辑前。

**触发条件**(任一即可,与节点是否在线无关):

- 文档归属某个接入节点 → 该节点下一轮同步(文件变更触发的监听同步,或默认 300 秒的定时对账);
- 文档归属 `local`(Hub 自身扫描的知识库目录)→ Hub 执行一次扫描(`POST /api/documents/scan`,
  仪表盘与文件树的扫描入口都会调)。

**机制(代码证据)**:

- 节点侧:`src/node/app/sync.py::classify_diff` 以**节点本地快照**为基准分类,本地文件没变就只报
  `path + hash`(hash-only);Hub 返回的 `rejected` 路径会被从快照里剔除
  (`_sync_documents` 的 `rejected_paths` → `next_snapshot`),于是下一轮该路径被当作「新增」、
  带全文重传。
- Hub 侧:`src/server/app/api/nodes.py::_sync_node_documents` 对 hash-only 条目,只在
  `old_doc.hash == doc.hash` 时跳过,否则计入 `rejected`(`hash mismatch`)等待重传。
  编辑后 Hub 的 hash 由 `services/document_writer.py` 重算,必然与节点本地 hash 不同 → 必被拒绝 →
  必被重传覆盖。
- `local` 侧:`src/server/app/services/indexer.py::sync_documents` 对扫描到的文档按 hash 比对,
  不一致就用磁盘内容覆盖 DB 内容;同时按「local 表里有、本次没扫到 → 删」推导删除。

**影响**:Hub 端的编辑对文件来源文档没有持久性保证。用户视角是「改了又变回去了」,
且界面上没有任何提示;离线节点只是让覆盖延后发生,不是不覆盖。

**状态**:已修(openspec 变更 `2026-09-30-fix-document-persistence`,2026-09-30)。

**修复方式**:文档新增内容来源 `origin`(`file` / `agent`)。写入口径
(`services/document_writer.py`)把新建与编辑的文档标记为 `agent`;`indexer.sync_documents`
的增量与删除推导收窄为只作用于 `origin="file"` 的文档;`_sync_node_documents` 对 `agent`
来源条目跳过并计入 `skipped`(不计入 `rejected`,避免节点每轮带全文重传),删除推导亦不删除这类文档。
即:Hub 写入过的文档,磁盘文件不再是权威。

**残留语义**:`agent` 转换是单向的——文件事件不会把文档拉回 `file`,因此磁盘文件从此
无法再更新该文档,且当前**没有文档删除入口**(REST / MCP / Web 均无),这类文档只能长期保留。
「从文件重新同步」的回退操作未实现,见该变更的 Non-goals。

---

## 2. Hub 或智能体新建的文档会被 Hub 扫描删除

**现象**:通过 `POST /api/documents` 或 MCP `create_document` 新建的文档,在 Hub 执行一次扫描后消失。

**触发条件**:文档归属 `local`(Hub 端 MCP / REST 创建时未带节点身份,`node_id` 落为 `local`),
且该路径在 Hub 知识库目录下**没有对应文件**。

**机制(代码证据)**:`src/server/app/services/document_writer.py::create_document` 只写数据库、
不落磁盘;而 `src/server/app/services/indexer.py::sync_documents` 的删除推导是
`set(existing.keys()) - scanned_paths`(local 作用域内「库里有、磁盘上没有 → 删」),
没有区分「文档来自文件扫描」与「文档由 Hub/智能体写入」。
节点作用域不受影响:节点只上报自己扫到的路径的删除,不会删掉自己从没见过的文档。

**影响**:批次 3「智能体写回」在 `local` 作用域下新建的文档不是持久的。

**状态**:已修(openspec 变更 `2026-09-30-fix-document-persistence`,2026-09-30)。

**修复方式**:`indexer.sync_documents` 的作用域收窄为 `origin="file"` 的 `local` 文档
(见问题 1 的修复方式)。`agent` 来源的文档既不参与内容覆盖,也不参与
`set(existing) - scanned_paths` 的删除推导,故智能体新建的文档不再被扫描清掉;
磁盘上出现同路径文件时,扫描跳过该条目并计入 `skipped`,不覆盖也不撞唯一约束。

**残留语义**:同问题 1——这类文档没有删除入口。

---

## 3. 无版本机制,写入一律「最后写入者胜」

**现象**:无法判断一次内容变化是「谁改的、基于哪个版本」;并发写入会静默覆盖。

**触发条件**:

- 两个管理员同时编辑同一文档 → 后保存的覆盖先保存的;
- Hub 端编辑与节点同步并发 → 见问题 1。

**机制(代码证据)**:`documents` 表(`src/server/app/models/document.py`)只有
`created_at` / `updated_at`,没有版本号、没有 ETag / `If-Match` 语义,`PUT /api/documents/{id}`
不做乐观锁校验;节点同步也不判断「Hub 的 `updated_at` 是否晚于本地文件」,
只比 hash 是否一致(`api/nodes.py::_sync_node_documents`)。

**影响**:冲突无法被发现、也无法被选择保留哪一版;节点侧「本地文件改过」与
Hub 侧「文档被编辑过」在协议上不可区分。

**状态**:待决(2026-09-30 用户决策:先记录问题,方案后续再议)。
