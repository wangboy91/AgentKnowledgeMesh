## Why

用户希望获授权后 A 可修改 B 的文件、B 可修改 A 的文件，原文件仍只有一台电脑持有；owner 主动删除源文件后，Hub 应同步失效，使另一台电脑不能再取得内容。现有写回只修改 Hub，且将 origin 设为 agent，不等于修改 owner 磁盘，也没有版本冲突保护。

## What Changes

- 新增独立、显式的 owner 远程写回候选通道：Hub 校验权限与 base revision/hash，唯一 owner Node 原子写盘并确认，Hub 提交版本后才报告保存成功。
- 稳定文件 ID、唯一 owner、代次、单调 revision 与内容 hash；记录本地与远程修改的版本元信息。按文件授权与可查询的幂等 operation ID，支持冲突、离线和结果未知。
- 源删除成为 tombstone，屏蔽所有新请求的内容读取并阻止旧同步、旧写操作复活；目录不可达不能推导为删除。
- 唯一用户待决：其他 Node 不保存原文件工作副本、Hub 可保留全文检索副本，还是 Hub 也不保存全文。建议前者作为最小方案，但没有替用户采纳；获准实施前不改现有存储策略。
- 本轮仅提案、状态与验收文档。未来实施只覆盖已注册的 Node 文件正文修改、版本记录和源删除传播，不增加远程创建/删除/移动、不迁移 Hub-only agent 文档、不自动镜像磁盘。

## Capabilities

### New Capabilities

- `owner-remote-writeback`: 唯一 owner 文件的显式授权写回、版本记录、操作状态与源删除可见性屏障。作为新通道契约约束其文件在所有读取入口的可见性。

### Modified Capabilities

无既有入口语义替换：旧 document-management 写回保留 Hub-only 行为，不升级为磁盘成功承诺。新能力对纳入管理的 owner 文件增加删除过滤；实施时须同步 API 文档并逐一验证既有读能力受该过滤约束。

## Impact

未来涉及 Hub document/nodes/auth/读入口与索引过滤、Node sync/transport/本地安全写盘、MCP 薄封装与 Web 版本/冲突状态。新增数据字段及协议需显式能力协商与迁移映射；旧 Node 无此能力不得写盘。无新 LLM、基础设施或付费依赖；本轮不修改源码、权限、配置、数据、正式 specs 或既有安全修复。
