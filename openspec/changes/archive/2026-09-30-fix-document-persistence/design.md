# document-persistence · 设计

## 背景

`documents` 表里目前只有 `node_id` 一个"归属"维度。它回答的是**文档属于谁**,
不回答**内容由谁负责**。两处"文件是权威"的推导因此无差别生效:

```
Hub 本机扫描      indexer.sync_documents
                  ├─ hash 不一致 → 用磁盘内容覆盖 DB 内容
                  └─ set(existing) - scanned_paths → 删除
节点磁盘同步      _sync_node_documents
                  ├─ 带全文 → 按 hash 比对插入/更新(覆盖)
                  └─ 无全文 + hash 不一致 → rejected → 节点下轮重传全文(覆盖)
```

`node_id` 无法承担这个判断:一篇 `local` 文档既可能来自 Hub 目录扫描,也可能是 MCP 新建的;
一篇节点文档既可能来自该节点的磁盘扫描,也可能是该节点的智能体经代理写入的。
两者在库里长得一模一样——这正是问题 1 / 问题 2 的根因。

## 决策

### D1 新增 `origin` 字段,取值为内容权威来源

```python
origin: Mapped[str] = mapped_column(String(8), default="file", nullable=False, index=True)
```

| 取值 | 含义 | 权威 | 文件事件(扫描 / 节点同步) |
| --- | --- | --- | --- |
| `file` | 内容由文件扫描派生 | 磁盘 | 可覆盖、可删除 |
| `agent` | 内容由 Hub/智能体写入,无对应磁盘文件 | Hub 库 | 不可覆盖、不可删除 |

命名避让:共享扫描器的 `ScannedDocument.source` 已被"知识根目录名"占用;
`derived_from` 已被 LLM wiki 批次 2 的溯源设计占用。故取 `origin`。

**默认值 `file` 是刻意的**:存量库的所有行都由文件扫描或节点上传产生(智能体写回是批次 3 才有的能力),
迁移时一律标 `file`,与迁移前的行为完全一致——不会因为迁移而让任何既有文档"突然不可删"。

### D2 写入即转 `agent`,不做编辑门控

`create_document` 一律 `agent`;`update_document` 把目标文档转 `agent`。

不选「禁止编辑 `file` 来源文档」:那会让 Web 编辑与 MCP `update_document` 对绝大多数文档失效
(库里绝大多数文档都是 `file` 来源),等于把批次 3 的写回能力废掉。用户要求的是"能读写",
所以选择"允许写,写后以 Hub 为准"。

REST `PUT /api/documents/{id}` 与 MCP `update_document` 共用 `document_writer.update_document`,
故两侧行为天然一致,不会出现"Web 改了算数、MCP 改了不算数"。

### D3 冲突消解规则:来源优先,单向

```
agent 文档  ← 文件事件(扫描 / 节点同步)   :忽略
file  文档  ← 文件事件                      :照常覆盖 / 删除
file  文档  ← Hub 写入(编辑)               :接受,并转为 agent
agent 文档  ← Hub 写入(再编辑)             :接受
```

规则是**单向的**:文件事件永远不能把 `agent` 文档拉回 `file`,但 Hub 写入可以把 `file` 文档推成 `agent`。
这保证"智能体写的东西不会自己消失",代价是**磁盘文件从此不再能更新该文档**——
在没有版本信息的前提下,两者无法兼得;选持久性是因为它直接对应用户诉求。

不做双向合并:那需要版本号 / ETag / 三方 diff,属问题 3,已在 proposal 的 Non-goals 中排除。

### D4 Hub 扫描:作用域从「`local` 全部」收窄为「`local` 且 `file`」

```python
existing = {doc.path: doc for doc in (
    await session.execute(
        select(Document).where(Document.node_id == "local", Document.origin == "file")
    )
).scalars().all()}
```

收窄 `existing` 的构造即可同时修好两个方向:删除推导 `set(existing) - scanned_paths`
自然不含 `agent` 文档(问题 2),内容覆盖循环也遍历不到它们(问题 1 的 `local` 分支)。

**额外要处理的唯一约束**:`(node_id, path)` 唯一。若磁盘上出现了与某 `agent` 文档同路径的文件,
扫描会走到"新文档插入"分支并撞唯一约束。因此单独查出 `agent` 路径集合,命中即跳过:

```python
if doc.path in agent_paths:
    stats["skipped"] += 1
    continue
```

`skipped` 让"配了目录却同步不进去"这件事在响应里可见,而不是静默。
该分支不是设计缺陷——它正是"磁盘文件不得夺回已被智能体改写的文档"这一规则在路径撞车时的表现。

### D5 节点入库:跳过而非 rejected

`agent` 来源条目**必须跳过,不能计 `rejected`**:

| 处理 | 后果 |
| --- | --- |
| 计 `rejected` | 节点把该路径移出快照 → 下轮重新分类为"新增" → 带全文重传 → 再被拒 → **每轮重传,永不收敛** |
| 跳过(计入 `skipped`) | 节点不把它视为失败 → 快照保留本地 hash → 下轮按 hash-only 上报 → 再被跳过 → **稳态,无重传** |

代价是每轮同步多一条 hash-only 条目(不传正文,流量可忽略)。这是可接受的。

同一规则覆盖三种入口:
- 带全文条目 → 跳过,不覆盖;
- hash-only 条目 → 跳过,不进 `rejected`;
- `deletions` 与隐式缺失推导 → `to_delete` 集合过滤掉 `agent` 来源路径。

### D6 `agent` 文档对显式 `deletions` 同样免疫

节点显式上报的 `deletions` 也是**文件系统事件**的产物(文件监听捕获 `Change.deleted`,
或全量对账发现文件消失),不是"用户要求删除这篇文档"的意图。既然 `agent` 文档的内容已不来自文件,
用文件消失来推断它应该消失,与 D3 的单向规则不一致。故一并免疫。

由此产生的缺口:**`agent` 文档没有任何删除入口**。当前 `/api/documents` 只有 GET/POST/PUT,
Web 也没有删除按钮。这是既有事实(批次 3 的写回同样"不提供删除",见 `docs/agent-write-back-design.md`),
不是本次引入的——本次只是让这类文档能长期存活,于是缺口变得可感知。
补删除能力涉及权限与作用域设计,列入 Non-goals,另行决策。

### D7 `origin` 暴露在响应里,但不进 MCP 文本输出

`to_dict` 增加 `origin`,REST 调用方与前端可据此判断文档是否受文件事件影响
(未来"编辑门控"或"来源徽标"的落点)。MCP 的工具输出文本**不改**:
`akm_shared/mcp_formatting.py` 是三形态共用的单源,改它要同时动 Hub MCP 与节点代理两侧的输出格式,
而智能体做检索/读写时不需要知道这个元信息——保持输出稳定,避免无收益的契约扰动。

## 迁移

复用既有轻量列迁移机制(`db.py::_COLUMN_MIGRATIONS`),与 `nodes.disabled` / `documents.rag_status` 同款:

```python
("documents", "origin", "ALTER TABLE documents ADD COLUMN origin VARCHAR(8) NOT NULL DEFAULT 'file'")
```

sqlite 与 postgres 两条 DDL 相同(都是 `VARCHAR` + `DEFAULT`,无需方言差异,但仍按既有结构分别登记)。
`create_all` 只建新表不改旧表,故存量库靠这条 DDL 补列;新建库由模型定义直接带上。

**已知不对称**:`index=True` 只对新建库生效(迁移只补列不建索引)。与 `rag_status` 迁移的既有情况一致,
不在本次修正——低基数列的索引收益本就有限,而过滤条件通常还带 `node_id`(已有索引)。

## 不在本次范围

- **版本机制**(问题 3):无版本号 / ETag / 乐观锁。`agent` 与 `file` 的冲突靠 D3 的来源优先消解,
  不做三方合并。两个编辑者之间的冲突仍为"最后写入者胜"。
- **文档删除能力**:REST / MCP / Web 均无入口,见 D6。
- **编辑门控与前端提示**:前端不据此置灰,也不提示"此文档已被智能体改写"。
- **"从文件重新同步"回退操作**:把 `agent` 文档转回 `file` 并让磁盘夺回权威,需要显式交互设计。
