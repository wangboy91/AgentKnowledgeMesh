# Proposal: add-hash-first-node-sync

## Why

节点每次同步都推送全部文档全文,流量与耗时为 O(全部字节);知识库增长后,心跳触发的同步将成为流量与延迟的主要来源,而绝大多数同步轮次实际没有任何变更。

## What Changes

- 节点维护本地同步快照(`<data>/sync_state.json`,path → hash),每轮扫描后与快照 diff:新增/变更文档上传**含全文**,未变文档只报 `{path, hash}`,消失文档进 `deletions` 列表
- **BREAKING(协议扩展,向后兼容)**:`PUT /api/nodes/{id}/documents` 请求体新增可选 `deletions` 字段,`documents[]` 条目的 `content` 变为可选
- Hub 入库规则扩展:未带 `content` 且库中 hash 一致 → 忽略;未带 `content` 且 hash 不一致 → 计入响应新增的 `rejected` 列表(节点下轮带全文重传);`deletions` 删除文档并清理向量
- 节点仅在收到 200 后更新快照;失败不动快照,下轮自动重试
- 旧版节点(始终发全文)行为不变,协议向后兼容

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `multi-node-sync`: 上传协议从"全量全文"改为"hash-first 增量",入库端点支持 `deletions` 与 `rejected` 语义

## Impact

- **node**:`sync.py` 增加 diff 与状态文件读写;上传 payload 分类构造
- **server**:`_sync_node_documents` 支持 content 缺省与 deletions;响应增加 `rejected`;向量维护通道复用现有 `deleted_ids`
- **兼容**:新旧节点可并存;Hub 先升级或后升级均可(旧节点不发新字段)
- **验证**:大目录二次同步上行流量应 ≈ 0(无变更时)
