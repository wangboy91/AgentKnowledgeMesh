# node-upload-batching

## Why

节点上传文档走的是**单次 PUT、全量打包**：一轮同步把本轮所有 `full_docs`（含全文）塞进一个 `PUT /api/nodes/{id}/documents` 请求。这在两种常见情形下会失败：

- **首次全量推送**：本地已有知识库（如 300+ 篇 Markdown）而 Hub 为空时，单个请求体可达数 MB 至数十 MB。部署在反向代理后的 Hub 会被 nginx 默认的 `client_max_body_size 1m` 拦下，返回 **413 Request Entity Too Large**——节点侧表现为 `⚠️ Document upload rejected (413)`，快照不更新，下轮重试仍 413，**知识库永远同步不进去**（死循环）。
- **大盘变更**：批量导入 / `git checkout` 大目录 / 迁移知识库时同理。

已实测复现（2026-09-30，公网部署 `nginx/1.26.3` + 304 篇知识库）：

```
📄 Found 304 documents
📤 Uploading: 304 full-text, 0 hash-only, 0 deletions
⚠️ Document upload rejected (413): <html>... 413 Request Entity Too Large ... nginx/1.26.3
```

值得注意的是 **hash-only 轮次不触发该问题**（不含正文、体积小），所以日常增量场景掩盖了这个缺陷，只有在"首次接入一个大知识库"时才暴露——而首次接入恰恰是最需要成功的时刻。

反向代理的 `client_max_body_size` 属于**部署侧配置**，把知识库规模上限交给运维去猜是不合理的；节点应当在小请求体内完成任意规模的知识库同步。

## What Changes

- **上传分批**：`DocumentSync._upload()` 改为按体积/条数把 payload 切分为多个请求串行发送，单请求体不超过配置上限，从而不依赖对端代理的 body 上限
- **新增配置项** `AKM_UPLOAD_BATCH_BYTES`（单请求体体积上限，默认 `512 * 1024` 即 512 KiB，可调）与 `AKM_UPLOAD_BATCH_DOCS`（单请求文档条数上限，默认 `50`，可调）；两者任一触顶即切批
- **切批规则**：`full_docs`（含全文，体积不定）与 `hash_only`（仅元信息，体积极小）分别处理——
  - 按体积累计，累计值超过 `batch_bytes` 即封批（**单篇超限的文档独占一批**，保证任何情况下都能推进，不会因单文件过大而卡死）
  - 按条数累计，超过 `batch_docs` 即封批
  - 两种上限同时生效，取先到者
- **`deletions` 只随最后一批发送**：避免多批重复删除；同时保证「列表缺失即删除」的隐式推导在每批都带 `deletions` 键（空列表）而被关闭
- **原子性保持**：任一批次失败（网络错误 / 非 200）则**整体视为失败**——已成功的批次不回滚（幂等，重传无害），但**本地快照一律不更新**，下轮按相同差异重试。这与既有语义「SHALL 仅在收到 Hub 成功响应(200)后更新本地快照」一致
- **`rejected` 跨批汇总**：所有批次的 `rejected` 合并后再决策快照，语义不变
- **统计跨批求和**：`created` / `updated` / `deleted` 为各批之和，日志输出仍是一行汇总
- **单批（小知识库）行为完全不变**：未触发任何上限时，请求数量、payload 结构与改动前逐字节一致

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `multi-node-sync`:`Node Document Upload` Requirement 增补分批上传约束（原 Requirement 的全部既有 Scenario 保留，新增 4 个 Scenario 描述分批语义）

## Impact

- `src/node/app/config.py`:新增 `upload_batch_bytes` / `upload_batch_docs` 配置项
- `src/node/app/sync.py`:`build_payload()` 拆出 `batch_payload(diff)` 生成批次序列；`_upload()` 改为 `_upload_batches()` 串行发批并汇总统计；`_sync_documents()` / `_sync_paths()` 改为消费汇总结果（快照更新逻辑的原子性语义不变）
- `src/node/tests/`:`test_sync.py` / `test_sync_local.py` 补分批切分与失败原子性用例
- 文档:`src/node/.env.example`（新增两个配置项说明）、`README.md`（节点配置表）、`docs/deployment.md`（FAQ 补 413 排查条目）
- **无对外契约变更**:仍调用既有 `PUT /api/nodes/{id}/documents`，payload schema 不变（只是分多次发），Hub 端零改动
- **部署侧不再强依赖代理配置**:`client_max_body_size` 小于默认批体积时同步仍可成功；文档中保留"代理 body 上限 ≥ 批体积可获得更少请求数"的调优提示
