# 正式/开发环境隔离方案

> 背景：节点当前与开发仓共用一份代码、一份凭证目录（`~/.akm-node`）、一份快照。
> 开发调试会直接影响正式同步——2026-09-30 首次接入实测中已暴露一次（快照串环境导致 304 篇被拒）。
>
> **状态（2026-09-30）**：已落地。唯一的代码改动（快照路径优先级）走 openspec 变更
> `2026-09-30-fix-node-state-isolation`；其余为部署编排（启动脚本 + 隔离配置目录），
> 见 §5 各步骤的「状态」标注。

## 1. 问题：现在为什么会互相踩

| 维度 | 现状 | 串环境的后果 |
| --- | --- | --- |
| **代码** | 正式与开发都用 `cd src/node && uv run akm-node` | 开发改 `sync.py` → 正式节点下次启动即用未验证的代码 |
| **凭证** | 共用 `~/.akm-node/.env`（`AKM_NODE_ID` / `AKM_NODE_TOKEN`） | 切 Hub 必须覆盖凭证 → 两套环境只能存在一套身份 |
| **快照** | 共用 `~/.akm-node/sync_state.json`（或仓内 `data/`） | 换 Hub 后旧快照致全量误判为"未变更"→ 全被 rejected（**已实际发生**） |
| **知识库** | 共用 `E:\works-doc` | 用户已确认**有意共用**，非问题 |

## 2. 已有的隔离地基（代码里已支持，但不够可靠）

`config.py` 支持两个进程环境变量：

```
AKM_NODE_ENV_FILE    # 覆盖凭证文件路径（默认 ~/.akm-node/.env）
AKM_NODE_STATE_DIR   # 覆盖快照所在目录（默认 ~/.akm-node）
```

**但 `AKM_NODE_STATE_DIR` 会被仓内 `data/` 抢占**（`state.py`，**已在本次变更中修复**）：

```python
def resolve_snapshot_path(repo_path: Path, user_path: Path) -> Path:
    return repo_path if repo_path.exists() else user_path   # 仓内存在即优先
```

即：只要在开发仓跑过一次节点（生成 `src/node/data/sync_state.json`），此后无论怎么设
`AKM_NODE_STATE_DIR`，快照都会落在**仓内**——两个环境继续串。且失败是静默的，
不会报错，只表现为"文档莫名没同步"。

> 修复后（`resolve_snapshot_path(..., explicit=)`）：显式设了 `AKM_NODE_STATE_DIR` 就以它为准，
> 不再探测仓内快照；未显式设置时行为与修复前逐字一致（存量开发状态无感迁移）。

> 附带事实：安装版（`uv tool install`）的 `BASE_DIR` 落在 venv 的 `site-packages`，那里不会有
> `data/sync_state.json`，所以它**恰好**避开了这个坑。但这只是巧合——不依赖它才是正解。

## 3. 目标形态

```
正式环境（隔离实例，本次要建的）
├── 命令       deploy/start-node-prod.ps1（固化隔离变量后调用全局 akm-node）
├── 代码       安装时的源码快照，不受开发仓后续改动影响
├── 凭证/配置   ~/.akm-node-prod/.env
├── 快照       ~/.akm-node-prod/sync_state.json
├── 知识库     E:\works-doc           ← 与开发共用（已确认）
├── 身份       AKM_NODE_ID 独立（避免两环境在 Hub 上争同一节点、互顶 token）
└── Hub        wss://gotitos.club/akm/ws（公网）

开发环境（保持现状）
├── 命令       cd src/node && uv run akm-node
├── 代码       开发仓工作区（随时可改）
├── 凭证/配置   ~/.akm-node/.env
├── 快照       ~/.akm-node/sync_state.json（或仓内 src/node/data/）
├── 知识库     E:\works-doc           ← 共用
└── Hub        ws://localhost:8000/ws（本地，待用户自启）
```

**要点**：同一份 `E:\works-doc` 被两个 Hub 各自的节点身份同步，互不干扰（文件只读源）。

## 4. 技术可行性（已实测）

`uv tool install .` 从源码安装时**能正确解析 path 依赖**：

```
Resolved 38 packages
 ~ akm-node==0.2.0 (from file:///E:/works-core/AgentKnowledgeMesh/src/node)
Installed 1 executable: akm-node
```

实测安装后 `site-packages/akm_shared/scanner.py` 含 `is_watchable_markdown`（5 处），
即 `akm_shared` 被正确打包并是最新版——**无需额外处理 path 依赖**。

安装路径：`C:\Users\wangb\AppData\Roaming\uv\tools\akm-node`（Windows）
可执行文件入口：`C:\Users\wangb\.local\bin\akm-node.exe`

> 试装验证已完成并卸载清理；正式安装见 §5。

## 5. 落地步骤

### 步骤 1：修 `state.py` 的快照抢占（**前提**，否则隔离不生效）— ✅ 已完成

`resolve_snapshot_path` 的优先级改为：**显式配置 > 仓内 > 用户目录**

```python
def resolve_snapshot_path(repo_path, user_path, explicit: bool = False):
    # 显式设了 AKM_NODE_STATE_DIR → 以它为准，不再被仓内 data/ 抢占
    if explicit:
        return user_path
    return repo_path if repo_path.exists() else user_path
```

显式标识 `USER_STATE_DIR_EXPLICIT = "AKM_NODE_STATE_DIR" in os.environ` 由 `config.py` 提供
（在模块级与 `USER_STATE_DIR` 同时机求值）。

**判定口径是「环境变量是否存在」，而非「值是否等于默认值」**——显式声明优先于任何隐式推断，
也便于"设成默认值"来主动关掉仓内抢占。

源码行为变更，已走 openspec：`openspec/changes/2026-09-30-fix-node-state-isolation/`（见 §7）。

### 步骤 2：建正式环境的隔离目录 — ✅ 已完成

```
~/.akm-node-prod/
├── .env               # Hub 地址 + 账号 + 知识库 + 独立 AKM_NODE_ID（首次启动写入 AKM_NODE_TOKEN）
└── sync_state.json    # 独立快照（首次同步成功后生成）
```

### 步骤 3：从源码安装正式实例 — ✅ 已完成

```bash
cd E:/works-core/AgentKnowledgeMesh/src/node
uv tool install . --reinstall    # --reinstall 保证幂等，升级即重跑此命令
uv tool update-shell             # 把 ~/.local/bin 加入 PATH（一次性）
```

产物落点：`%APPDATA%\uv\tools\akm-node`（含 `app` 与 `akm_shared`，path 依赖被正确解析），
可执行文件 `~/.local/bin/akm-node.exe`。

> 注意：`uv tool install .` 不带 `--reinstall` 也可，但升级时必须带（否则 uv 认为已装最新）。
> 若 `~/.local/bin` 未在 PATH，脚本会自动回退到绝对路径，不阻塞启动。

### 步骤 4：写正式环境启动脚本 — ✅ 已完成

`deploy/start-node-prod.ps1`（Windows）与 `deploy/start-node-prod.sh`（Linux / macOS / Git Bash）。

关键点：脚本只设 **两个进程环境变量**（`AKM_NODE_ENV_FILE` + `AKM_NODE_STATE_DIR`）——
其余（Hub 地址、知识库、账号、身份）都在 `~/.akm-node-prod/.env` 里自包含。
这样脚本本身不含任何环境特有信息，换机器只需换那份 `.env`。

**为什么不能省掉脚本**：`config.py` 在模块 import 时读这两个变量，早于 `.env` 加载，
写进 `.env` 不生效且不报错。脚本的存在意义就是把这个坑固化掉。

### 步骤 5：首次登录正式 Hub — ✅ 已完成（自动登录，无需交互）

`~/.akm-node-prod/.env` 里配了 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD`，
启动时自动登录换取凭证并写回同文件，无需人工执行 `login`：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\start-node-prod.ps1
```

实测（2026-09-30）：

```
🔐 AgentKnowledgeMesh Node v0.2.0
📡 Hub URL: wss://gotitos.club/akm/ws
💻 Node: WANG-Work-PC-Prod (windows)
📁 Knowledge: E:\works-doc
✅ Registered with Hub: 335d4bab-3604-4f5a-ab94-187e0bb64108
📄 Found 304 documents
📤 Uploading: 0 full-text, 304 hash-only, 0 deletions in 7 batches
👁 监听中: E:\works-doc (防抖 3s)
📤 Synced 304 documents: created=0 updated=0 deleted=0 rejected=0
```

> 第二次及以后启动是 hash-only 轮次（`0 full-text`），`rejected=0`。作为对照，
> 修复前那次同样的 304 篇是被 Hub 全量 `rejected` 的——这正是快照串环境的后果。

## 6. 验证要点

| 验证项 | 判据 | 实测结果（2026-09-30） |
| --- | --- | --- |
| 快照独立 | 正式的快照落在 `~/.akm-node-prod/sync_state.json` | ✅ 生成，304 条 |
| 隔离生效 | 正式节点跑完后，`~/.akm-node/` 与 `src/node/data/` **未被改动** | ✅ 两个文件 md5 与运行前完全一致；`data/` 未被创建 |
| 路径解析 | 显式指定状态目录时不被包内快照抢占 | ✅ 仓内/包内人为放置 `sync_state.json` 后仍走显式目录；不设变量时旧行为不变 |
| 身份独立 | 启动日志 `Node:` 行显示正式实例的名字 | ✅ `WANG-Work-PC-Prod` |
| 同步正确 | Hub 侧文档数 == 本地篇数 | ✅ Hub 304 == 本地快照 304 |
| 代码隔离 | 改开发仓 `sync.py` 后重启正式节点，行为**不变** | 机制上成立（实例是安装时的副本）；未做破坏性实测 |

## 7. 变更分流

| 改动 | 是否走 openspec | 理由 |
| --- | --- | --- |
| `state.py` 快照优先级修正 | ✅ **走**（`2026-09-30-fix-node-state-isolation`） | 源码行为变更（改变快照落盘位置） |
| 启动脚本（`deploy/start-node-prod.*`） | ❌ 直接改 | 部署编排，非代码行为 |
| 安装步骤写入 `docs/deployment.md` §2.6 | ❌ 直接改 | 文档 |

## 8. 已决事项

- [x] 正式实例的命令名：**沿用全局 `akm-node` + 专用启动脚本 `deploy/start-node-prod.*`**。
      没有改 `pyproject.toml` 去造第二个可执行名——隔离边界在"启动脚本设的环境变量"，
      不在可执行文件的名字；加别名反而多一处需要同步维护的 CLI 表面。
- [x] 隔离目录名：`~/.akm-node-prod`（与默认 `~/.akm-node` 同构，一眼看出是正式那套）。
- [x] 第二个正式 Hub 预留位：**暂不做**。当前正式 = `gotitos.club/akm`；
      将来若需要多套正式环境，换一份 `.env` 即可，无需改代码。
- [x] 开发实例的 Hub：计划连**本地 Hub**（`ws://localhost:8000/ws`，用户自启）。
      当前 `~/.akm-node/.env` 仍指向 gotitos，**切换时机由用户决定**——
      若两个实例同时连同一个 Hub，会用两个身份把同一份知识库各推一遍（Hub 侧出现重复副本）。

## 9. 方案对比（为何选"独立安装实例"）

| 方案 | 代码隔离 | 状态隔离 | 改代码 | 评价 |
| --- | --- | --- | --- | --- |
| **A. uv tool 安装实例** | ✅ | ✅ | 否 | **选中**——唯一实现"正式不受开发影响" |
| B. 环境变量分身 | ❌ | ✅ | 否 | 代码仍是同一份，开发改动照样影响正式 |
| C. 代码层 `--profile` | ✅ | ✅ | ✅ | 更优雅但要改代码；可作后续演进（本方案的 §5 步骤 1 已是其最小子集） |
