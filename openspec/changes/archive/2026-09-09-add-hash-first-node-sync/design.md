# Design: add-hash-first-node-sync

## Context

现状:节点 `sync.py` 每轮把扫描到的全部文档(含 content)PUT 到 Hub;Hub `_sync_node_documents` 已按 `(node_id, path)` + hash 做服务端增量,但"未变文档的全文"仍每次在网络上传输。方案详见 [docs/technical-design.md](../../../docs/technical-design.md) §4。

## Goals / Non-Goals

**Goals:**
- 无变更同步轮次的上行流量降为 O(文档数)(仅 path+hash)
- 删除操作显式化(不再依赖"列表缺失=删除"的隐式推导)
- 新旧节点与 Hub 任意先后升级均兼容

**Non-Goals:**
- 节点间 P2P 同步、断点续传、分块上传(单文档 ≤ 10MB 上限不变)
- 快照的服务端托管(快照仅存节点本地;丢失即首轮全量重建,可接受)

## Decisions

1. **快照存 `<data>/sync_state.json`**(路径锚定 node 包 data 目录,gitignore):`{path: hash}` 扁平结构,读写原子(临时文件 + replace)。备选 SQLite(重,弃)。
2. **diff 以快照为基准,不以库为基准**:节点无法也不应查询库状态;hash 不一致但无全文的情形由 Hub 以 `rejected` 反馈,节点下轮自然重传(因为快照在成功前不更新)。
3. **响应新增 `rejected` 而非返回 4xx**:部分失败不应让整批同步失败;节点把 rejected 条目按"未同步"处理(快照不含它们 → 下轮带全文)。
4. **deletions 显式列表替代隐式缺失删除**:避免快照与库短暂不一致时的误删;`Hub Node Document Ingestion` 中"列表缺失即删除"仅对**携带 content 的旧协议**保留(兼容)。
5. **向量清理复用现有 `deleted_ids` 后台通道**,不新增机制。

## Risks / Trade-offs

- [快照与库不一致(如库被手工清理)] → 节点快照认为已同步、库无此文档:本期接受(rejected 机制兜底 hash 不一致;路径缺失且无 content 记 rejected,下轮带全文补齐)
- [状态文件损坏] → 读取失败按空快照处理,触发全量重建(自愈)
- [时钟/竞态] → 快照仅在 200 后写入,天然幂等

## Migration Plan

1. 先升 Hub(兼容旧节点全量协议)→ 再升各节点
2. 回滚:节点回退后恢复全量推送,Hub 新协议字段被忽略,无需数据迁移

## Open Questions

无。
