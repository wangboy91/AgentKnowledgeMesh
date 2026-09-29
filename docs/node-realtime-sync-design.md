# 节点实时同步与服务化 · 架构与实现设计

> 状态:**已实施、端到端验证通过、openspec 变更已归档**(`2026-09-29-add-node-file-watch`)。
> 日期:2026-09-29。本文是批次 1(见 §1.3)的设计输入,实施按 `docs/conventions/workflow.md` §2 走 openspec 变更 `add-node-file-watch`;delta 已合入 `openspec/specs/multi-node-sync`。
> 上游需求:多电脑知识共享(文档分散在多台机器,机间无法共享,各机智能体无法取用)。产品定位见 [product-overview.md](product-overview.md)。

## 1. 背景与范围

### 1.1 要解决的问题

现状:节点(Node)只在**进程启动**和**Hub 主动请求**两个时机同步本地文档。用户在任意一台电脑上新增/修改文档,Hub 与其余节点都无从知晓——知识共享实际是"手动挡":必须重启节点,或由管理员在 Web 节点页手点「同步」。

目标:让"文档改动"成为**事件**而非"下次重启时的偶然发现"。改完文件,秒级到达 Hub,其他电脑上的智能体立即检索得到。

### 1.2 现状基线(与本文相关)

| 环节 | 现状 | 位置 |
| --- | --- | --- |
| 扫描 | 递归 `rglob("*.md")`,跳过相对路径中含 `.` 开头的项,单文件上限 10MB,多根目录时以目录名作路径前缀 | `src/shared/akm_shared/scanner.py` |
| 差异分类 | hash-first:`added/changed` 带全文,`unchanged` 仅报 `path+hash`,`removed` 进 `deletions` | `src/node/app/sync.py:36` |
| 快照 | `{path: hash}`,原子写入(临时文件 + `os.replace`),读失败按空快照自愈 | `src/node/app/state.py` |
| 触发 | ① `connect()` 成功后一次 ② 断线重连后一次 ③ Hub 发 `sync_request` | `src/node/app/runner.py:63-70`、`transport.py:121` |
| 上传 | `PUT /api/nodes/{id}/documents`,节点 token 鉴权 | `sync.py:146`、`server/app/api/nodes.py:272` |
| 运行形态 | 前台常驻,`Ctrl+C` 退出;断线 5 秒重连 | `__main__.py`、`runner.py:87` |

**核心缺口**:全仓无文件监听、无定时器。文档变更不产生任何事件。

### 1.3 批次定位与本文范围

多机共享痛点的最短路径是「批次 1 → 批次 3」:

| 批次 | 内容 | 与本文关系 |
| --- | --- | --- |
| **1** | **节点文件监听 + 服务化** | **本文覆盖** |
| 2 | wiki 页数据模型(`doc_type` / `derived_from` / stale) | 后续,LLM wiki 线 |
| 3 | MCP 写工具(智能体可写回) | 后续,痛点线收口 |
| 4 / 5 | 可插拔 distiller / 自动化治理 | 后续,首个 LLM 依赖 |

**本文做**:节点侧文件变更监听 → 自动触发增量同步;定时全量对账兜底;节点服务化托管模板。

**本文不做**(明确划出,避免范围蔓延):

- 非 Markdown 格式接入(PDF/Word/HTML 转换)——独立批次,转换器目前只服务 Web 上传通道
- MCP 写工具、Hub 侧反向下发、多机可见性隔离——分别属批次 3 与未排期项
- 排除规则的**用户可配置化**(`.akmignore`)——本文仅实现内置规则,文件化留待有真实需求时再做
- Hub 端任何改动——本变更**纯客户端行为**,服务端零改动

## 2. 目标架构

### 2.1 触发模型

把同步的触发源从"进程生命周期事件"扩展为三类并存,互为补充:

```
① 变更事件(实时)   watchfiles 监听 → 过滤 → 防抖 → 增量同步
② 定时对账(兜底)   每 N 秒全量 scan + hash diff → 增量同步
③ 既有触发(保留)   启动 / 重连 / Hub sync_request
```

三者最终都汇入同一个 `DocumentSync.sync_documents()`,**复用现有 hash-first 差异分类与快照语义**,不新增上传协议。

### 2.2 进程内位置

`HubClient.run()` 当前并行跑两个 task(心跳、消息处理)。监听循环作为**第三个 task** 并列,互不阻塞:

```
run() 循环
  ├─ connect() → 注册
  ├─ task: _heartbeat_loop()          既有
  ├─ task: transport.handle_messages() 既有
  ├─ task: _watch_loop()              新增(文件变更)
  ├─ task: _reconcile_loop()          新增(定时对账)
  └─ sync_documents()                  既有(首次全量)
```

设计原则:**监听任务异常不得拖垮心跳与消息链路**。监听循环内部捕获全部异常并退避重试,`asyncio.wait(FIRST_COMPLETED)` 的既有语义不变。

### 2.3 并发与一致性

同一时刻只允许一个同步在跑(监听触发、对账触发、Hub 请求可能同时到来)。用 `asyncio.Lock` 串行化 `sync_documents()` 调用;后到的请求**合并等待**而非排队执行,避免事件风暴引发重复上传。

快照语义不变:**仅在 Hub 返回 200 后更新快照**;失败不动快照,下轮自然重试。因此并发保护的目的是省流量,不是保正确性。

## 3. 详细设计

### 3.1 选型:watchfiles

| 候选 | 评价 |
| --- | --- |
| **watchfiles** ✅ | 基于 Rust `notify`,原生 async(`awatch()`),自带 `debounce` 参数;uvicorn 已依赖,不引入新生态 |
| watchdog | 线程模型,与现有 asyncio 编排(心跳/消息均为 task)风格不一致,需跨线程桥接 |
| 轮询 | 仅作为容器场景的降级路径,不作主路径 |

依赖新增:`src/node/pyproject.toml` 加 `watchfiles>=0.21`。

### 3.2 监听范围与过滤

监听根目录 = `settings.knowledge_paths`(即 `AKM_KNOWLEDGE_ROOTS`,默认 `~/Knowledge`)。

- **只监听存在的目录**:不存在的根在启动时剔除,避免 `awatch` 直接抛错;全部不存在时监听任务进入空转等待(不报错退出)
- **扩展名**:仅 `.md`,与 `scanner.py` 一致
- **内置排除目录**:`.git`、`.venv`、`__pycache__`、`node_modules`、`dist`、`build`、`.idea`、`.vscode`
  - 注意:`scanner.py` 已跳过相对路径中以 `.` 开头的项,但 `node_modules` 不以点开头,必须显式排除
- **大小上限**:复用 `DEFAULT_MAX_SIZE_BYTES`(10MB),超限文件忽略并记一条日志

过滤规则用 `watchfiles` 的 `watch_filter` 回调实现,与 `scanner.py` 的判定保持**同一套语义**——两处不一致会导致"监听到了但扫描不到"或反之的诡异行为。建议把共用判定抽到 `akm_shared`(如 `is_watchable_markdown(path, roots)`),供 scanner 与监听复用。

### 3.3 防抖与写入稳定

- **防抖**:直接用 `awatch(..., debounce=AKM_WATCH_DEBOUNCE_SECONDS * 1000)`,默认 3000ms。编辑器保存、`git checkout`、批量复制都会产生密集事件,聚合后再触发
- **写入稳定检查**:防抖只保证事件聚合,不保证文件写完(大文件复制场景)。触发前对目标文件做两次 `stat`(间隔 300ms),`st_size` 与 `st_mtime_ns` 均未变化才纳入本轮;不稳定则跳过,**由定时对账兜底**,不阻塞本轮其他文件
- **删除事件**:`Change.deleted` 直接进 `deletions`,无需稳定检查

### 3.4 增量路径(避免全量重扫)

监听触发时,若只改动 1~2 个文件,不必重扫整个知识库:

1. 由变更路径集合 → 定位所属知识根 → 计算相对路径
2. 仅对变更文件执行 `stat` + 读取 + `compute_hash`
3. 与快照比对,构造 `SyncDiff`(复用 `classify_diff` 的语义,但输入是"局部文档集 + 快照")
4. 走既有 `build_payload` + `_upload`

**关键约束**:局部 diff 不得产生 `deletions`——快照中存在但本轮未扫描到的路径**不代表被删除**,只有监听明确捕获到 `deleted` 事件的路径才进 `deletions`。这是局部同步与全量同步的核心区别,实现时须显式区分,否则会误删其他文件。

对账路径(§3.5)仍走全量 `scan_knowledge_roots` + `classify_diff`,语义与现状完全一致。

### 3.5 定时对账

- 间隔 `AKM_WATCH_RECONCILE_SECONDS`,默认 **300 秒**
- 直接调用既有 `sync_documents()`(全量扫描 + hash diff),无新逻辑
- 存在的理由:监听会丢事件(跨平台差异、缓冲区溢出、网络文件系统),对账保证**最终一致**
- 代价:全量扫描需读取并哈希全部文件。中小知识库(数千个 md)为百毫秒~秒级;超大知识库可将间隔调大或设为 `0` 关闭(仅靠监听,接受丢事件风险)

### 3.6 服务化(托管模板)

现状要求前台常驻(`Ctrl+C` 退出),多机部署时这是第一劝退点。安装脚本在完成 `uv tool install` 后**打印对应平台的托管模板**,不自动注册(避免安装脚本做系统级改动):

| 平台 | 模板 |
| --- | --- |
| Linux | systemd user unit:`~/.config/systemd/user/akm-node.service`,`ExecStart=%h/.local/bin/akm-node`,`Restart=always`,`WantedBy=default.target` |
| macOS | launchd plist:`~/Library/LaunchAgents/com.akm.node.plist`,`KeepAlive=true` |
| Windows | 计划任务:`Register-ScheduledTask`,触发器"用户登录时",`RestartCount` 3 |
| 通用 | `pm2 start akm-node --name akm-node`(已有 pm2 的用户) |

服务化属 `deploy/` 编排改动,**按 `workflow.md` §2 直接改**(不走 openspec),与本文的代码变更分开提交。

### 3.7 容器场景的降级

Windows / macOS 宿主的 Docker bind mount **不传播 inotify 事件**,节点容器内的监听会静默失效。处理:

- 容器方式(`deploy/docker-compose.node.yml`)默认关闭监听(`AKM_WATCH_ENABLED=false`),依赖定时对账
- 启动日志明确打印"监听已关闭,依赖 N 秒对账"的提示,避免"以为在实时同步"的误解
- Linux 宿主可开启监听(内核原生支持 bind mount 事件传播)

## 4. 配置项

全部走环境变量(`AKM_` 前缀),与现有 `NodeSettings` 一致;用户级配置在 `~/.akm-node/.env`。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AKM_WATCH_ENABLED` | `true` | 文件监听总开关;容器场景置 `false` |
| `AKM_WATCH_DEBOUNCE_SECONDS` | `3` | 事件防抖窗口 |
| `AKM_WATCH_RECONCILE_SECONDS` | `300` | 定时对账间隔;`0` = 关闭 |
| `AKM_WATCH_EXCLUDE` | 空 | 追加排除目录名(逗号分隔),在内置规则之外 |

## 5. 兼容性与边界

- **Hub 端零改动**:上传协议、鉴权、快照格式全部沿用,服务端不需要升级
- **新旧节点共存**:老节点行为不变;新节点仅多出触发源
- **快照格式不变**:仍是 `{path: hash}`,无需迁移
- **已知限制**:
  - 网络文件系统(SMB/NFS)的变更事件不可靠 → 依赖对账
  - 首次启动仍是一次全量上传(hash 为空),与现状一致
  - 单机知识库超过数十万文件时,对账成本显著,应调大间隔或关闭

## 6. 验证口径

**单测**(`src/node/tests/`):

- 过滤判定:扩展名、隐藏项、内置排除目录、大小上限
- 局部 diff 语义:**不产生 deletions**(防误删,最关键的一条)
- 防抖聚合:连续事件只触发一次同步
- 写入不稳定时跳过、不阻塞其他文件
- 并发保护:同时触发只跑一次上传

**实测**(Hub + Node 同机):

1. 启动节点 → Web 端可见节点与文档
2. 新增一个 `.md` → **目标:Hub 端 `updated_at` 更新延迟 < 10s**
3. 修改该文件 → 同上
4. 删除该文件 → Hub 端文档消失
5. 关闭监听(`AKM_WATCH_ENABLED=false`)→ 验证对账路径同样能在 N 秒内收敛
6. 断网 30 秒后恢复 → 变更不丢,重连后补齐

**回归**:`src/node` 与 `src/server` 既有 pytest 全绿(server 侧本变更不动代码,跑一遍确认无副作用)。

## 7. 待决与后续

- **排除规则的配置文件化**(`.akmignore`):本文只做内置规则。若实际使用中出现"某些目录不想同步"的反复需求,再开变更
- **多格式接入**:wiki 线的前置(语料质量决定提炼层上限),独立批次
- **Hub 侧反向下发**:节点只能推不能拉,离线场景拿不到其他机器的文档;未排期
