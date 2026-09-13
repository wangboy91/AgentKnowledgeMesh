# Tasks: add-hash-first-node-sync

## 1. Hub 端协议扩展

- [x] 1.1 `NodeDocumentItem` 模型 `content` 改为可选;请求模型增加 `deletions: list[str]`;`_sync_node_documents` 实现三分支(带全文入库 / 无全文 hash 一致忽略 / 无全文不一致记 rejected)+ deletions 删除;响应增加 `rejected`
- [x] 1.2 兼容回归:旧式全量 payload(全部含 content、无 deletions)行为与现状一致;新增 pytest 用例(`tests/test_node_sync.py` 扩展):三分支、deletions、rejected、作用域隔离,`uv run pytest` 全绿
- [x] 1.3 rejected 条目的下轮补传验证:模拟节点先报 hash 不匹配、再带全文重传,断言入库成功

## 2. 节点快照与 diff

- [x] 2.1 新增 `app/state.py`:快照读写(原子写、损坏按空快照自愈);单测覆盖正常读写、损坏文件、首次为空
- [x] 2.2 `sync.py` 实现 diff 分类(added/changed → 含全文;unchanged → 仅 path+hash;removed → deletions);单测覆盖三类与空目录
- [x] 2.3 上传 payload 构造与"仅 200 后更新快照";单测:失败响应后快照不变、成功后快照等于本轮扫描

## 3. 端到端验证

- [x] 3.1 Hub+Node 联调(Hub 运行中):首轮全量 → 二轮无变更(日志确认仅 hash 上行)→ 修改一个文件(仅该文件含全文)→ 删除一个文件(deletions 生效,Hub 检索不再命中)
- [x] 3.2 大目录流量对比:构造 200+ 文档目录,记录二轮同步 payload 字节数,验证 ≪ 全量(验收口径:无变更轮次 < 文档数 × 200 字节)

## 4. 收尾

- [x] 4.1 `uv run pytest` 全量回归;`uv run akm-node` 冒烟
- [x] 4.2 更新 `docs/api-reference.md` §8 协议示例(rejected/deletions)与 README 节点说明;openspec verify
