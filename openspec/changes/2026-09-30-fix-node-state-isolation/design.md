# fix-node-state-isolation — 技术设计

## 1. 背景与目标

节点要从"开发工具"变成"正式服务"，同时保留开发调试能力。两者共处同一台机器、同一个仓库时，
必须在**代码 / 凭证 / 快照**三个维度各有独立选择。本变更只处理**快照**维度里的一处缺陷：
`AKM_NODE_STATE_DIR` 的显式指定被包内快照静默抢占。

完整隔离方案见 `docs/env-isolation-design.md`；本变更对应其"步骤 1"，是该方案唯一的代码改动。

## 2. 现状与缺陷

`src/node/app/config.py`（模块级，import 时求值）：

```python
USER_ENV_FILE  = Path(os.environ.get("AKM_NODE_ENV_FILE")  or Path.home() / ".akm-node" / ".env")
USER_STATE_DIR = Path(os.environ.get("AKM_NODE_STATE_DIR") or Path.home() / ".akm-node")
```

`src/node/app/state.py`：

```python
_REPO_SNAPSHOT_PATH = BASE_DIR / "data" / "sync_state.json"

def resolve_snapshot_path(repo_path: Path, user_path: Path) -> Path:
    return repo_path if repo_path.exists() else user_path
```

`BASE_DIR` 在两个场景下含义不同：

| 运行方式 | `BASE_DIR` | 包内快照路径 | 结果 |
| --- | --- | --- | --- |
| 开发仓 `uv run akm-node` | `src/node/` | `src/node/data/sync_state.json` | 跑过一次即存在 → **抢占** |
| 安装版（`uv tool install`） | venv 的 `site-packages/` | `site-packages/data/...`（不存在） | 落 `USER_STATE_DIR` |

**缺陷只在开发仓场景显形**，但后果一致：`AKM_NODE_STATE_DIR` 形同虚设。且失败是静默的——
快照串环境不会报错，只表现为"文档莫名没同步"（2026-09-30 实测：304 篇被 Hub 全量 `rejected`）。

> 附带信息：安装版恰好因 `BASE_DIR` 指向 `site-packages` 而天然避开此缺陷。但**不能依赖这个巧合**——
> 一旦 `uv tool install` 的构建形态变化（例如将来把 `app` 装成带 `data/` 的资源），
> 或用户在仓内用 `python -m app` 跑正式实例，缺陷立刻复现。

## 3. 设计决策

### 3.1 判定口径：环境变量「是否存在」，而非「是否等于默认值」

```python
# config.py
USER_STATE_DIR_EXPLICIT = "AKM_NODE_STATE_DIR" in os.environ
```

| 方案 | 语义 | 评价 |
| --- | --- | --- |
| **存在性判定**（选中） | 设了就听你的 | 显式声明优先于隐式推断；可解释、可测；设成默认值即可主动屏蔽包内抢占 |
| 取值比对 | 值 ≠ 默认值才算显式 | 无法表达"我就要用户目录，别抢"；语义绕 |

代价：不能用"设成默认值"来表达"我要包内优先"。该诉求无实际场景——包内优先正是要否定的行为。

### 3.2 参数传递：加显式维度，不改默认分支

```python
# state.py
def resolve_snapshot_path(repo_path: Path, user_path: Path, explicit: bool = False) -> Path:
    """选择快照位置:显式指定状态目录时以它为准,否则包内已有快照优先(存量迁移)."""
    if explicit:
        return user_path
    return repo_path if repo_path.exists() else user_path

DEFAULT_SNAPSHOT_PATH = resolve_snapshot_path(
    _REPO_SNAPSHOT_PATH, USER_STATE_DIR / "sync_state.json", USER_STATE_DIR_EXPLICIT
)
```

- `explicit` 默认 `False` → **不设环境变量时逐字保持旧行为**，既有测试与存量环境零影响。
- 保持函数纯函数（不读 `os.environ`）→ 三种优先级组合都能直接单测，无需操纵进程环境。

### 3.3 不引入 `AKM_PROFILE`

"一个变量派生全部路径（env / state / 日志 / 知识库）"的 profile 机制更优雅，但：

- 引入新的配置面与命名空间，需要与既有 `AKM_NODE_*` 变量定义互斥规则；
- 与本次要修的缺陷不成比例——一个 `if` 即可；
- 可以作为后续演进（本变更是其最小子集：显式 > 隐式）。

## 4. 隔离方案的落点（非本变更，随同一提交）

本变更只动节点代码。隔离方案的其余部分是**部署编排**，按 `docs/conventions/workflow.md` §2 直接落地：

| 产物 | 作用 |
| --- | --- |
| `deploy/start-node-prod.ps1` / `.sh` | 固化 `AKM_NODE_ENV_FILE` + `AKM_NODE_STATE_DIR` 两个**进程环境变量**后调用全局 `akm-node` |
| `~/.akm-node-prod/.env` | 正式实例自包含配置：Hub 地址、账号、知识库目录 |
| `uv tool install .` | 从源码构建出与开发仓解耦的独立实例（实测可正确解析 `akm-shared` path 依赖） |

**为什么两个变量必须在启动脚本里设，而不能写进 `.env`**：`config.py` 在**模块 import 时**用
`os.environ.get()` 读取它们，早于 pydantic-settings 加载 env 文件。写进 `.env` 不会生效——
这是本方案里最容易踩的坑，脚本的存在意义正是把这件事固化下来。

## 5. 验证基线

| 验证项 | 判据 |
| --- | --- |
| 单测 | `cd src/node && uv run pytest` 全绿（含新增优先级组合用例） |
| 零回归 | 未设 `AKM_NODE_STATE_DIR` 时快照路径与改动前一致 |
| 实机隔离 | 正式实例运行后 `~/.akm-node/.env` 与 `src/node/data/` 均未被改动 |
| 快照独立 | 正式实例快照落在 `~/.akm-node-prod/sync_state.json` |
| 同步正确 | Hub 侧该节点文档数 == 本地 Markdown 篇数 |
| 双实例并存 | 正式实例运行时，开发实例仍可正常启动与同步（各自快照互不覆盖） |

## 6. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 显式指定后路径变化，用户预期落点不一致 | 日志/文档说明；`AKM_NODE_STATE_DIR` 本就是"用户级运行数据目录"的既定覆盖项 |
| 已有环境显式设了该变量却期望包内优先 | 无实际场景；如需回退，删掉该环境变量即恢复旧行为（无需改代码） |
| 安装版构建形态变化导致 `BASE_DIR` 落点改变 | 本变更使安装版不再依赖 `BASE_DIR` 的巧合 |
