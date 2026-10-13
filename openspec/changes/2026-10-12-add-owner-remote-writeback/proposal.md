## Why

用户希望获授权后 A 可修改 B 的文件、B 可修改 A 的文件，原文件仍只有一台电脑持有；owner 主动删除源文件后，Hub 应同步失效，使另一台电脑不能再取得内容。现有写回只修改 Hub，且将 origin 设为 agent，不等于修改 owner 磁盘，也没有版本冲突保护。

## What Changes

- 新增独立、显式的 owner 远程写回候选通道：Hub 校验权限与 base revision/hash，唯一 owner Node 原子写盘并确认，Hub 提交版本后才报告保存成功。
- 稳定文件 ID、唯一 owner、代次、单调 revision 与内容 hash；记录本地与远程修改的版本元信息。按文件授权与可查询的幂等 operation ID，支持冲突、离线和结果未知。
- 源删除成为 tombstone，屏蔽所有新请求的内容读取并阻止旧同步、旧写操作复活；目录不可达不能推导为删除。
- 存储选择已确认：正文仅由归属 Node 持久保存，Hub 只存身份、owner、授权、版本、hash、删除及操作状态等元数据；不持久化全文、可读 chunk、历史正文或 embedding。另一端仅按需内存查看/编辑，不自动保存正文工作副本。
- 本轮先更新提案，再按新授权实施最小闭环。未来实施只覆盖已注册的 Node 文件正文修改、版本记录和源删除传播，不增加远程创建/删除/移动、本轮不迁移 Hub-only agent 文档、不自动镜像磁盘。

## Capabilities

### New Capabilities

- `owner-remote-writeback`: 唯一 owner 文件的显式授权写回、版本记录、操作状态与源删除可见性屏障。作为新通道契约约束其文件在所有读取入口的可见性。

### Modified Capabilities

当前只读 profile 的例外约束以 ADDED delta 表达，保留所有原 requirement/scenario，正式基线本轮不归档修改。

- `document-management`: strict profile 隔离旧文档读写/扫描。
- `multi-node-sync`: strict profile 独立元数据 WS，禁用旧全文同步。
- `keyword-search`: Hub 路径元数据检索与在线 owner 正文检索边界。
- `vector-search`: strict profile 不初始化向量库，不新增 embedding/chunk。
- `agent-context-api`: strict profile 隔离旧正文 Context 输出。
- `mcp-integration`: strict profile HTTP/stdio/Node 正文工具关闭。
- `knowledge-indexing`: strict profile 不新增 Hub 内容索引。
- `document-conversion`: strict profile 隔离旧转换/临时正文入口。

## Impact

未来涉及 Hub document/nodes/auth/读入口与元数据检索、在线 owner 正文检索及旧内容索引停用、Node sync/transport/本地安全写盘、MCP 薄封装与 Web 版本/冲突状态。新增数据字段及协议需显式能力协商与迁移映射；旧 Node 无此能力不得写盘。无新 LLM、基础设施或付费依赖；本轮修改最小链路源码及文档，不改真实权限/配置/用户数据，不覆盖既有安全修复。

## 已确认约束与本轮边界

用户原话：“我要 正文只在归属电脑，Hub 协调访问，另一台电脑不落盘 这种效果”。确认来源：原任务 01a12e2b-e602-7495-a7dc-533559b1403b 的用户 turn 01a12f5e-29fc-72c1-9ee8-2ee5daad0bdd（item 01a12f5e-2a27-74bd-8102-653274f6ffbd），由本轮委托提供的 transcript_evidence。

Hub 允许按需内存中转正文，但队列、日志、审计、错误报告、缓存和临时文件均不得持久落正文。Hub 提供元数据检索，正文检索由在线 owner 执行；owner 离线无法读取/编辑/正文检索，超时如实返回不可用或 unknown。

AKM 只保证自己可控制且验证过的存储与客户端路径。第三方 Agent、扩展、操作系统及手动复制可能留存正文；持久会话客户端与严格要求冲突，MCP 接入不天然符合约束，未经验证的正文接入默认不启用。用户已批准最小 owner 链路实施，完整迁移/永久清理未批准；现有 Hub 副本的迁移/永久删除须另行设计和确认，本轮不执行旧数据清理。


最小实现已获授权；Windows 并发安全预验证未通过，目前等待明确本地写入并发域，不能降低 CAS/路径安全要求。最新已交付默认关闭的独立 owner 只读/权限/删除代码与隔离验证；写回未启用，完整闭环仍未完成。


本次先实施独立只读 profile：稳定 owner 元数据、在线内存读取/单文件搜索、显式读取授权、离线/不可达明确失败、源删除墓碑与严格模式全读取屏障。新 `/api/owner-files` 和 `/owner-ws` 默认关闭；旧全文仍存但被严格模式隔离，不清理既有数据。写回明确不支持，完整任务不标成完成。
