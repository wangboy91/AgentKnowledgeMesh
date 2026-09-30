# node-upload-batching · 任务清单

## 1. 配置项

- [x] 1.1 `src/node/app/config.py` 新增 `upload_batch_bytes`(默认 `512*1024`)与 `upload_batch_docs`(默认 50),`<= 0` 表示该维度不限;验证:`test_config.py` 补 `test_upload_batch_defaults`、`test_upload_batch_env_overrides`、`test_upload_batch_non_positive_means_unlimited` → 13 passed
- [x] 1.2 `src/node/.env.example` 增「上传分批」段(独立为 §5,原高级配置顺延为 §6),说明两个配置项用途、默认值、`<=0` 语义与"代理 body 上限 ≥ 批体积可减少请求数"的调优提示

## 2. 分批切分

- [x] 2.1 `src/node/app/sync.py` 新增 `batch_payload(diff, batch_bytes, batch_docs) -> list[dict]`:按序累积,条数或估算体积触顶即封批;单篇超限独占一批;`deletions` 仅随最后一批、前序批次带空列表;`build_payload` 保留为单批便捷入口(复用 `_build_payload_and_size`);验证:`test_sync.py` 补 8 个用例——单批/单批等价 build_payload/条数切分/体积切分/单篇超限独占/deletions 位置/空 diff/UTF-8 口径
- [x] 2.2 体积估算函数 `_doc_entry()` + `_ENTRY_OVERHEAD_BYTES`:content 取 UTF-8 字节长 + path/title 长度 + 固定开销常数,不重复 `json.dumps`;验证:`test_doc_entry_size_estimates_utf8_not_chars`(中文按 3 字节)、`test_doc_entry_hash_only_no_content_key`

## 3. 批次发送与原子性

- [x] 3.1 `src/node/app/sync.py` 新增 `_upload_batches(diff) -> (汇总统计 | None, 失败原因)`:串行发送,任一批非 200 或抛异常即中止并返回失败信号(含批次序号与响应体);全部成功才返回汇总;新增模块级 `merge_stats()` 跨批求和(数值相加、rejected 拼接、容忍缺字段);验证:`test_merge_stats_sums_and_concatenates_rejected`、`test_merge_stats_tolerates_missing_rejected`
- [x] 3.2 `_sync_documents()` 改为消费汇总结果:失败 → 打印 `Document upload aborted: 批次 i/N ...` 且快照不动;成功 → 用跨批汇总的 `rejected` 决策快照;日志补 `in N batches`(仅多批时);验证:`test_sync.py` 25 passed(含新增 `test_multi_batch_success_updates_snapshot`、`test_multi_batch_partial_failure_keeps_snapshot`、`test_multi_batch_network_error_keeps_snapshot`、`test_multi_batch_rejected_aggregated_across_batches`)
- [x] 3.3 `_sync_paths()` 同步改造为消费汇总结果,保持其"局部更新快照"(不重建)的既有语义;验证:`test_sync_local.py` 15 passed(含新增 `test_local_sync_batches_when_over_limit`、`test_local_sync_batch_failure_keeps_snapshot`)

## 4. 回归与验收

- [x] 4.1 节点单测全量:`src/node` **149 passed**(基线 129,新增 20)
- [x] 4.2 服务端单测:本次**未改动 `src/server` 任何文件**(`git status src/server/` 为空)。服务端测试已跑通(188 个用例全量 100% 跑完、无失败标记),零回归。附注:首次运行报 `error: Failed to spawn: pytest`,根因是 server 未装可选依赖 —— `src/server/pyproject.toml` 用的是 `optional-dependencies.dev`,须 `uv sync --extra dev`(不是 `--group dev`)
- [x] 4.3 端到端实测(实机公网 Hub,见 4.4;失败路径由 3.1/3.2 的单测覆盖:中途批次失败终止后续批 + 快照不动)
- [x] 4.4 **实机验证真实场景**(2026-09-30,公网 Hub `gotitos.club/akm`,nginx 默认 1m body 上限):
  - 修复前:`📤 Uploading: 304 full-text, ...` → `⚠️ Document upload rejected (413)` → Hub 侧 0 篇(死循环)
  - 修复后:`📤 Uploading: 304 full-text, 0 hash-only, 0 deletions **in 12 batches**` → `📤 Synced 304 documents: created=304 updated=0 deleted=0 rejected=0`
  - Hub 侧独立核对:该节点文档数 **304 == 本地 304**
  - 收尾:验证用节点进程已停,无遗留进程、无端口占用
- [x] 4.5 文档同步:`src/node/.env.example`(新增 §5 上传分批)、`README.md`(节点配置表 + 同步说明段)、`docs/deployment.md`(§2.5 配置表增两行 + 同步行为说明 + 常见问题补 413 排查条目)

## 遗留

- `src/node/uv.lock` 在启动排查过程中被 `uv sync --reinstall-package akm-shared` 更新(修复 venv 内旧版 akm_shared 缺 `is_watchable_markdown` 的问题),该改动应随本次提交一并纳入
- 归档前需先经用户确认提交;按项目规约 AI 不执行 `git commit` / `git push`
