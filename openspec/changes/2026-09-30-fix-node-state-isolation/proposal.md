# fix-node-state-isolation

## Why

节点要作为**长期在线的正式服务**运行，同时开发者仍要在同一个仓库里跑调试实例。当前两者会互相踩，
根因是「一份身份」而非「两份身份」——代码、凭证、快照三个维度都没有隔离手段。其中**快照**维度已经
在 2026-09-30 首次接入正式 Hub 的实测中真实踩到：旧的 `sync_state.json`（属于另一台 Hub）让节点
误判 304 篇文档"均未变更"，只上报 `{path, hash}` 不带正文，被 Hub 全量计入 `rejected`，
直到清空快照才暴露下一个问题。

代码里其实已经预留了两个进程环境变量作为隔离地基：

```
AKM_NODE_ENV_FILE    # 覆盖凭证文件路径（默认 ~/.akm-node/.env）
AKM_NODE_STATE_DIR   # 覆盖快照所在目录（默认 ~/.akm-node）
```

`AKM_NODE_ENV_FILE` 的优先级是可用的（`config.py` 在模块加载时读进程环境变量，用户级文件覆盖开发仓 `.env`）。
**但 `AKM_NODE_STATE_DIR` 会被包内快照静默抢占**（`src/node/app/state.py`）：

```python
def resolve_snapshot_path(repo_path: Path, user_path: Path) -> Path:
    return repo_path if repo_path.exists() else user_path   # 包内存在即优先
```

即：只要在开发仓跑过一次节点（生成 `src/node/data/sync_state.json`），此后**无论怎么设
`AKM_NODE_STATE_DIR`，快照都会落在包内**——两个环境继续共用同一份快照，隔离失效且**不报错**，
用户只能观察到"文档莫名没同步"。这是本次要修的点。

**影响面**：没有它，"正式实例 + 开发实例并行"不成立。隔离方案（`docs/env-isolation-design.md`）
的其余部分（独立安装实例、独立凭证目录、启动脚本）都能落地，唯独快照这一环会被静默串掉。

**期望行为**：显式指定状态目录时，快照路径**必须**以它为准；未指定时保持既有行为不变
（包内既有快照优先，否则落用户目录），存量开发状态无感迁移。

## What Changes

- **`resolve_snapshot_path` 增加"显式指定"维度**：新增参数标识 `AKM_NODE_STATE_DIR` 是否由进程环境
  变量显式设置；显式设置时直接返回 `user_path`，不再探测包内 `data/sync_state.json`。
- **`config.py` 暴露该标识**：新增 `USER_STATE_DIR_EXPLICIT`（由 `"AKM_NODE_STATE_DIR" in os.environ`
  求得），供 `state.py` 使用。读取点在模块级，与 `USER_STATE_DIR` 保持同一时机与口径。
- **默认行为不变**：未设置 `AKM_NODE_STATE_DIR` 时，解析结果与改动前逐字相同——包内快照存在则沿用，
  否则落 `~/.akm-node/`。这保证既有开发环境与已安装实例的行为零变化。

**语义选择**：判定依据是**进程环境变量是否存在**，而不是"值是否等于默认值"。因此把
`AKM_NODE_STATE_DIR` 显式设成 `~/.akm-node`（等于默认值）也会被视为显式指定、从而屏蔽包内抢占——
这是刻意的：显式声明优先于任何隐式推断，也便于用"设成默认值"来主动关掉包内抢占。
代价是无法用"设成默认值"表达"我要包内优先"，但那种诉求没有实际场景（包内优先正是要否定的行为）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `multi-node-sync`：Requirement「Node Document Upload」补充**快照位置的解析优先级**
  （环境变量 > 包内既有快照 > 用户目录），并说明显式指定时不得被包内快照抢占

## Impact

- `src/node/app/config.py`：新增 `USER_STATE_DIR_EXPLICIT` 常量（不改变 `USER_STATE_DIR` 现有取值）
- `src/node/app/state.py`：`resolve_snapshot_path` 增加显式维度；`DEFAULT_SNAPSHOT_PATH` 计算方式随之调整
- `src/node/tests/test_state.py`：新增优先级组合的单元测试
- `docs/env-isolation-design.md`：步骤 1 从"待办"改为"已实现"（该文档为本次隔离方案的说明稿）
- `deploy/`：新增正式实例启动脚本（部署编排，非代码行为，不属本次 openspec 范围，随当次提交说明）
- **不改动** `src/server`、`src/web`、`src/shared`
- **对外契约**：无变化。这是节点进程内的路径解析行为，不涉及任何 API / 消息协议字段
- 与在制变更无文件重叠

## Non-goals

- **不做 `--profile` / `AKM_PROFILE` 的完整多环境抽象**：本次只修"显式指定被静默忽略"这一处缺陷。
  一个变量管全套派生路径的 profile 机制是更优雅的演进方向，但会引入新的配置面与迁移成本，另行决策。
- **不做凭证文件的同类加固**：`AKM_NODE_ENV_FILE` 已是"显式 > 用户级 > 开发仓"的正确优先级，无此缺陷。
- **不做多实例互斥 / 单实例锁**：两个实例同时运行是隔离方案支持的正常场景（同一份知识库、
  各自 Hub、各自快照），不做进程互斥。
- **不改动快照文件格式**（`{path: hash}`），不做快照版本号或迁移工具。
