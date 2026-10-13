## Context

见 proposal.md。实际文件证据：Document.content 保存 Hub 全文；document_writer 只入库并置 origin=agent；节点上传按 node_id/path 更新且跳过 agent。现有整数文档 ID 不应直接当稳定源文件身份。这是待迁移的现状，不是已确认严格模式的目标。未来严格模式须停用旧 Hub-only 正文写入/全文上传旁路；本轮不改现有运行行为。

## Goals / Non-Goals

目标：授权后双向操作各自 owner 的 Markdown 正文，记录可审计版本，owner 删除后阻断再次取用。每个文件恰有一个 owner，A 和 B 可分别拥有不同文件；其他 Node 不落原文件工作副本。读取时的暂时内存缓冲不构成自动镜像。

边界：已获最小代码链路实施授权，不调整真实 ACL，不远程创建/删除/移动，本轮不迁移 agent 数据，不建设 Wiki、离线编辑、全量基座，不复原旧方案附件。历史正文若保留只能在 owner，保留策略单独设计，不默认永久清除。

## Decisions

### 身份、授权与路径

候选映射为 file_id（不可变 UUID）、owner_node_id、root_id、owner 相对路径、generation、revision、hash；绑定到现有 Document.id 作为兼容查询映射。重命名只能由 owner 可信映射保持 ID，不能凭相同 hash 猜同一文件；无法确认则新身份。删除后同路径重建是新 ID/代次，旧授权不继承。owner 转移不在范围内。

授权限定已认证主体、单文件 ID/代次、read 或 update_content、有效期/撤销；owner 配置的可写根是第二道约束。Hub 验证当前角色、授权、Node 未禁用；viewer、只读 token、匿名无写权限，节点 token 不因在线自动获得跨节点权限。owner 显式授权与当前主体写资格同时满足，admin 也不得绕过 owner 可写根。只记录授权契约，本轮不创建授权。

Node 从已登记 root+file_id 解析路径，不接受任意目标绝对路径；拒绝 ..、盘符/UNC、NTFS ADS、Windows 大小写别名冲突、symlink/junction/reparse point 越界。提交前重新检查父目录/目标解析及文件身份，使用可防替换竞态的安全句柄/锁；平台不能保证边界就拒绝写入，不以一次 resolve 检查代替安全性。

### 写回、版本与失败恢复

候选请求包含 file_id、generation、base_revision、base_hash、operation_id、new_content；调用者不能改 owner/path。Hub 原子校验并预留操作，发送到已认证 owner 会话。owner 对文件串行化处理，与本地编辑共同参与实际字节 hash 比较；外部编辑器竞争无法安全仲裁时返回冲突，禁止覆盖未知修改。同目录临时文件写入、flush、原子替换及持久操作日志用于恢复；owner 的操作日志仅记录元数据/请求 hash，不记正文；原子替换临时正文文件只允许位于 owner，故障残留由后续授权恢复流程管理。Hub 预留操作不得将 new_content 持久入队。

Node ack 包含同一 operation_id、代次、实际结果 hash 与落盘确认；Hub 幂等提交 revision、hash、版本元信息及 owner 报告的检索可用状态元数据，再置 committed。只有此时 REST/MCP/UI 报保存成功；索引异步尚未完成时明确 pending，不能返回过期内容当最新版本。写入不再转成 Hub-only agent。

状态为 pending → owner_applied → committed，或 rejected/conflict；超时为 unknown，不能当失败或成功。按原 operation_id 查询/reconcile，重试同 ID+同请求摘要返回同一结果，不同摘要拒绝。双方持久化操作状态，重启后查询 owner 日志，避免 ack 丢失后重复执行；操作日志保留范围外的旧 ID 不得当新请求执行。owner 离线拒绝新写且不排队，未知已发操作例外须对账。权限撤销在派发及 owner 实际执行前重新检查；已落盘后不承诺撤销回滚，通过对账给出事实。

revision 对每次确认的正文变化和删除递增；hash 基于实际 UTF-8 字节。版本列表至少含 revision、hash、时间、来源、主体、operation_id，不存凭据。Hub 仅保留版本元数据，历史正文如有保留只能由 owner 持有且受当前读取权限与删除屏障控制；本片不提供历史恢复，避免绕过删除。

### 源删除与读取屏障

owner 可访问完整根并确认文件不存在/可信删除事件，经 ID、代次与序列上报，Hub 提交 tombstone 后阻断新请求。无法在离线时立即知道物理删除，保证时间点是 Hub 确认删除；界面应显示未同步/owner 离线。根断挂载、权限不足、部分扫描或超时只标不可达，禁止推导删除。

删除和写回按文件序列化：已落盘写可先提交再 tombstone；删除先提交则旧 ack/upsert 一律不能激活内容。列表/树/详情/关键词与向量搜索/片段/Context API/API/MCP/历史正文/操作查询均在返回前检查 active+代次。索引清理可异步，读取屏障必须立即生效，分页/缓存/后台重建也不能旁路。tombstone 及操作元信息保留用于拒绝延迟消息；新建同路径需新 ID/代次和重新授权。已下载外部副本无法抹去，删除也不等于永久销毁全部历史。

### 已确认的存储与客户端约束

正文仅归属 Node 持久保存；Hub 只存身份、owner、授权、版本、hash、代次、tombstone 与操作状态等非正文元数据。删除前后都不允许 Hub 保留全文、可读 chunk、历史正文、内容摘要等替代副本。本最小提案不引入 Hub embedding：其派生自正文，存在信息推断/泄露风险，不能自行解释为满足用户约束；若未来提出须独立评估和授权。

Hub 可在有界请求内存中转正文，请求结束释放缓冲。正文不得写入 Hub 的持久队列、请求/响应日志、审计、异常堆栈附件、缓存、临时文件或遥测。操作摘要为规范化请求字段加 new_content 的 hash，不是正文节选；错误返回和审计仅有 ID/状态。owner 离线不持久排队正文，重启恢复只查操作元数据，不能从 Hub 重放正文；必要时客户端以同 operation_id 和摘要重新提交到在线 owner。

Hub 仅做元数据检索（ID、路径等显式非正文元数据，路径本身亦须权限保护，不从正文抽取摘要）。全文关键词查询由在线 owner 执行，命中片段仅按需内存返回，Hub 不保存正文索引/向量。跨 owner 检索若部分节点离线须标明覆盖不完整，不能把缺席当无命中；正文请求超时如实返回不可用，写超时维持 unknown。

AKM Web/Node 客户端只在内存查看和编辑正文，禁用正文下载/离线缓存及 localStorage、IndexedDB、浏览器 Cache API、Service Worker 缓存、磁盘编辑草稿、正文会话日志。响应使用禁止缓存策略，但不能据此保证任意浏览器或操作系统不落盘。请求元数据和凭证按原安全规则管理，不允许正文混入 URL/错误/日志。

承诺仅限 AKM 控制并验证过的应用持久化路径；无法自动保证第三方 Agent 的聊天历史/工具日志、浏览器扩展、OS swap/crash dump 或用户复制不留存。客户端若持久记会话正文就不满足严格另一电脑不落盘。正文工具接入必须声明并验证“不持久化工具输入/输出/会话正文”的能力与信任条件；未验证则默认不开放正文工具，也不宣称合规，元数据能力可单独开放。若需求包含 OS 层绝对零磁盘留痕，在验证主机前标为未满足，不用模型/供应商配置替代本轮工作。

## Risks / Trade-offs

- 磁盘与 Hub 无跨机事务 → 可查询 unknown、持久幂等日志与对账；绝不提前宣称成功。
- 本地编辑/删除与网络延迟竞争 → CAS、代次及 tombstone 返回屏障；不能保证未联网 owner 的删除即时传播。
- 历史保留泄漏 → 正文所有返回入口共享当前可见性判定；独立物理清除策略待后续授权。

## Migration Plan

本轮已批准最小链路实施；旧数据迁移清理仅设计，不执行永久删除。开关只能阻断新副本，不能证明现存副本消失。

1. 只读盘点：Hub Document.content、全文/向量库与可读 chunk、历史正文、agent-only 文档、缓存/队列、日志/审计/错误报告、临时文件、备份/导出/快照及可控客户端会话/草稿；记录位置、保留期限和是否含正文，不将正文复制到盘点报告。
2. 确立 owner：建立稳定 ID/代次映射，逐项核验 owner 磁盘实际字节与 hash。Hub-only agent 内容没有可验证 owner 时暂不迁入严格模式，不凭 node_id 假定磁盘有文件；提出受控导出/落 owner 方案，实施前再批准。
3. 先阻断新增 Hub 正文：能力协商、上传改为元数据、停用旧 Hub-only 写入口和正文索引任务，统一正文内存转发/日志脱敏/客户端禁缓存。迁移隔离期间旧库不向严格通道提供正文，但仍不能宣称“Hub 已无正文”。
4. 提交清理计划供届时用户确认：列明当前全文、chunk、向量/索引、历史、备份、快照、日志与临时副本的处理范围。永久删除现存数据需届时明确用户确认；不自动新建 Hub 全文备份，已有备份的保留与销毁也须逐项确认。合法保留副本存在时，严格存储迁移只能标未完成。
5. 获准后才处理旧副本，并以隔离合成正文标记和元数据 hash 核验全部列明存储面：数据库列、内容索引、队列/日志、备份/历史、缓存/临时文件、应用客户端会话/草稿无正文。审核范围外/不可访问存储列为未验证，不用开关或逻辑置空充当物理清除证明；加验证读取/编辑只经在线 owner。
6. 逐文件开启并验收断线、超时、冲突、重启幂等和 tombstone 全读取停供；目录不可达不批量删除。更新 API/用户/工程文档以及既有能力 delta，保留 ID、代次、授权和操作元数据用于防复活。

回退仅关闭新通道或恢复元数据操作，不自动恢复 Hub 正文存储/旧全文上传，不恢复 tombstone 前的可读状态。用户已批准最小链路实施，永久清理未授权；旧数据迁移步骤保持未执行。


## 实施预验证阻塞（2026-10-12）

用户已授权尽早完成最小 owner 链路，不再需要重复询问该授权。实施前 Windows 临时文件实验尝试：CreateFileW 以只共享读取的目标句柄阻断外部写入/删除，再以 SetFileInformationByHandle(FileRenameInfoEx, REPLACE_IF_EXISTS | POSIX_SEMANTICS) 原子替换。实际返回 False / WinError 32，目标字节保持 old。该实验不证明所有 Windows API 都无法实现，只证明此次方案未通过。

普通读取 hash 后 os.replace 存在校验与替换之间的外部编辑/路径替换间隙，不能满足本提案的安全契约。未接入的本地原型已经移除，没有交付或启用不满足契约的写回实现。

当前需明确本地写入的并发域：初版仅管理由 AKM 排他写入、所有本地编辑也经 AKM 的文件（普通编辑器文件暂不开放写回），还是继续研究普通编辑器文件的安全写回并在验证前拒绝远程写入。已发送此具体问题，未选择默认答案；存储选择已经确定，不再待确认。不能将该问题改写成整体实施授权未获得。旧数据迁移/永久清理仍另行确认。


## 当前已实施独立只读切片

写回安全设计仍未通过，按最新授权先交付不依赖它的读取/权限/删除链路。默认 `AKM_OWNER_READONLY_ENABLED=false`；显式开启时 Node 不运行旧全文同步，Hub 全面隔离旧全文 REST/WS/MCP，新增 owner_files/owner_read_grants/owner_versions 仅存元数据。旧库仍保留，不把读取隔离当物理清除。

Node 状态库持久记录 file_id、root/path、generation、revision、hash、大小和墓碑；重启身份保持，删除后同路径重建新身份/授权。本片重命名按旧身份删除与新身份创建处理，不承诺跨路径保持同 ID；owner 转移未支持。仅完整可达根确认缺失，任一读取/遍历/根边界失败保留旧记录并标不可达。显式根、1 MiB UTF-8 Markdown、每 manifest 最多 5000 条，超限不当删除。丢失 Node 状态后不自动恢复旧绑定。

Windows 读取打开祖先目录及目标的 GENERIC_READ、FILE_SHARE_READ、OPEN_EXISTING、FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT 句柄；检查 FileAttributeTagInfo 拒绝重解析点，读取期间保持句柄且不共享写入/删除，结束释放。POSIX 分支用逐层 dir_fd + O_NOFOLLOW；当前真实执行验证仅 Windows。

读取须既有凭证、owner 单文件 read grant（绑定代次、有期限和撤销），以及部署方已核验的 memory-only 主体白名单。白名单缺省空，不信任客户端自报“不落盘”。Node 正文 RPC 与文件搜索仅在内存；返回前新 DB session 再检查墓碑/授权/身份/owner 状态/版本，并检查正文 hash。离线/超时 503，版本冲突 409，源删除 410，未授权 403。写回 501（viewer/只读 token 403），Node write action 不支持，绝不写磁盘或报告保存成功。旧 Web 页面不新增接入，第三方正文 MCP 保持关闭。

本切片仅单进程 Hub 内存连接表，不声称多 worker 路由可用；没有历史正文、内容持久队列或 embedding。多 worker、完整 Web、写回 operation_id/CAS、真实跨电脑及 PostgreSQL 验收仍未完成。

## Windows 写回资料取舍（父会话提供官方核验摘要）

[ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew) 的目标 DELETE 访问与禁止 FILE_SHARE_DELETE 的保护句柄冲突，关句柄再替换重新引入竞态。[CreateFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea) 的共享规则可保护普通 I/O 临界区，但按名称替换没有 expected hash/identity CAS。[LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex) 不覆盖映射 I/O，不能直接当通用解。未仓促引入 oplock/TxF。

候选同一排他句柄原位写入可结合 owner 恢复日志与 [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers) 提供恢复；它不保证崩溃时原路径总为完整旧版或新版，也不阻止外部旧缓冲稍后覆盖。此处只记录父会话研究与取舍，没有采用该方案或修改既定原子保存契约。后续必须用确定性的 busy、hash 冲突、临界区写/删/rename 拒绝、双请求、映射/重解析、丢 ack 与恢复不覆盖后来编辑测试；压力测试无复现不足以证明安全。

原失败实验精确前提：目标 CreateFileW desired_access=GENERIC_READ(0x80000000)、share=FILE_SHARE_READ(1)、OPEN_EXISTING(3)、OPEN_REPARSE_POINT(0x00200000)；源临时文件 desired_access=DELETE(0x10000)、share=7、OPEN_EXISTING；SetFileInformationByHandle information_class=FileRenameInfoEx(22)、Flags=REPLACE_IF_EXISTS|POSIX_SEMANTICS(3)，绝对目标路径 UTF-16LE。返回 False、GetLastError=32；关闭句柄后目标内容校验为 old。后续没有重复该失败实验。

## 排他同句柄原位写入隔离实验（2026-10-12，产品未启用）

可重跑脚本：src/server/scripts/verify_owner_exclusive_write.py。命令：在仓库根运行 `src/server/.venv/Scripts/python.exe src/server/scripts/verify_owner_exclusive_write.py`（或进入 src/server 后运行 `.venv/Scripts/python.exe scripts/verify_owner_exclusive_write.py`）。只使用 TemporaryDirectory 自建合成 Markdown，子进程 probe/interrupt 模式也限制到带本脚本标记的临时目录；不导入产品 app，不访问默认数据库、真实目录或凭据，不改变产品开关。

精确参数：CreateFileW desired_access=GENERIC_READ|GENERIC_WRITE(0xC0000000)，share=0，OPEN_EXISTING(3)，FILE_FLAG_OPEN_REPARSE_POINT(0x00200000)。同一目标句柄内先 GetFileInformationByHandle 核验 volume/file index 与非 reparse/directory，再 ReadFile/计算 base hash 并检查进程内 base_revision；完成确定性外部探针后复核保护期间 hash；SetFilePointerEx(0)→WriteFile→SetEndOfFile→FlushFileBuffers→同句柄 ReadFile 验证。关闭句柄前不按路径重开。实验 revision 仅在进程内，不是产品持久 CAS/receipt。

| 确定性场景 | 实际结果 |
| --- | --- |
| 目标已有外部 READ|WRITE、share=7 句柄 | 新排他 OPEN_EXISTING 返回 busy / WinError32，原字节保持 |
| 校验 hash 后暂停，独立进程 write/truncate/delete/rename | 全部被拒，WinError32；保护期间 hash 不变 |
| 同期独立进程 MoveFileExW 替换（REPLACE_EXISTING|WRITE_THROUGH） | 被拒，WinError5；无锁对照同操作成功，保护期间 hash 不变 |
| 两个同 base 请求，第一持句柄后第二尝试 | 第一写入并复读确认，第二 busy；第一结束后原 base 重试 conflict，进程内 revision 只增一次 |
| 外部先保存再请求 | base hash 不符，conflict，保留外部已修改字节 |
| 子进程原位写前4字节、FlushFileBuffers 后 os._exit(23) | 原路径出现 NEW!INAL-COMPLETE 混合字节，明确不是完整旧版或新版；没有恢复日志，不恢复或报告成功 |

最终实验命令退出0，5组观察全部符合断言；此处“通过”包含非原子性的失败反例，不等于产品安全写回已就绪。首轮退出1因为断言把所有拒绝硬编码为错误32，但替换实际错误5；首轮原始日志保留，随后增加无锁成功对照并接受明确拒绝码5/32/33，不隐藏该差异。最终原始 JSON：.workbuddy-ai/verification/owner-exclusive-write-experiment-2026-10-12.json；首轮：owner-exclusive-write-experiment-attempt1-2026-10-12.json。

未实现/未验证：owner 恢复日志、崩溃恢复和不覆盖后来外部修改、持久 revision/operation receipt、丢 ack 幂等、映射 I/O、此前编辑器旧缓冲在锁释放后的再保存、恶意祖先 reparse 替换及真实多机。没有重复旧“保护句柄+原子替换”的失败实验。原子保存契约没有被暗中改为可恢复原位保存，产品 PUT content 仍501。

最小取舍：保持当前完整旧/新字节原子契约就继续关闭写回；若用户明确接受原位异常中断可能暴露部分内容、随后仅提供可恢复处理的较弱性质，才可下一步设计 owner 本地先 flush 恢复日志与持久 receipt、并逐项验证恢复不覆盖外部新编辑。建议目前维持只读交付和写回关闭，不替用户采纳较弱保证，也不要求所有本地编辑默认改走 AKM。
