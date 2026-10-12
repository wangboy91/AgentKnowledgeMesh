# node-state-isolation · 任务清单

## 1. 配置层暴露「显式指定」标识

- [x] 1.1 `src/node/app/config.py` 新增 `USER_STATE_DIR_EXPLICIT = "AKM_NODE_STATE_DIR" in os.environ`,与 `USER_STATE_DIR` 同处模块级、同时机求值;验证:`test_state.py::test_default_snapshot_path_follows_process_env`(子进程内求值,避开 import 缓存)与 `::test_default_snapshot_path_not_explicit_without_env`(不设变量时标识为 False)
- [x] 1.2 `USER_STATE_DIR` 取值逻辑保持不变(仅新增标识,不改既有解析);验证:既有 `test_config.py` 全绿

## 2. 快照路径优先级修正

- [x] 2.1 `src/node/app/state.py::resolve_snapshot_path` 增加 `explicit: bool = False` 参数,显式指定时直接返回 `user_path`;验证:`test_state.py::test_explicit_state_dir_wins_over_repo_snapshot`
- [x] 2.2 `DEFAULT_SNAPSHOT_PATH` 传入 `USER_STATE_DIR_EXPLICIT`;验证:`test_state.py::test_default_snapshot_path_follows_process_env`(端到端:设变量时默认快照即为该目录且标识为显式)
- [x] 2.3 未显式指定时行为逐字不变:包内存在 → 用包内;不存在 → 用用户目录;验证:`test_state.py::test_not_explicit_keeps_legacy_behaviour`(两种组合 + 默认参数)、`test_explicit_state_dir_wins_when_repo_snapshot_absent`

## 3. 验证基线

- [x] 3.1 `cd src/node && uv run pytest` → **154 passed**(基线 149 + 本次新增 5),连跑 6 轮均 `failures=0 errors=0`
  - 期间发现并修掉一个自引入的**偶发失败**:初版接线测试为验证"仓内存在快照"而往 `src/node/data/` 写临时文件并起两个子进程,一次全量运行中该用例(第 113 个)失败且未能复现。已重构为**不触碰仓库工作区**、只起一次子进程读取 `(USER_STATE_DIR_EXPLICIT, DEFAULT_SNAPSHOT_PATH)` 的形态;重构后 6/6 轮全绿,且 `src/node/data/` 不再被测试创建
- [x] 3.2 openspec 校验:`openspec` CLI 本机当前不可用(`/c/nvm4w/nodejs/openspec` 已不存在),改为手工核对场景集合(见 3.3)与工件结构
- [x] 3.3 与基线场景名逐个核对:MODIFIED 的 `Node Document Upload` **原 12 个 Scenario 全部保留**,新增 4 个,共 16 个 → 通过
- [x] 3.4 实机路径解析验证(安装实例 + 开发仓两种 `BASE_DIR` 形态):
  - 安装实例(包内 `site-packages/data/` 人为放快照):不设变量 → 包内;设变量 → `~/.akm-node-prod` ✅
  - 开发仓(仓内 `data/` 存在,即修复前必串的场景):不设变量 → 仓内(存量无感);设变量 → `~/.akm-node-prod` ✅

## 4. 隔离方案落地(部署编排,非本变更的代码范围)

- [x] 4.1 新增 `deploy/start-node-prod.ps1` 与 `deploy/start-node-prod.sh`:固化 `AKM_NODE_ENV_FILE` 与 `AKM_NODE_STATE_DIR` 两个**进程环境变量**后调用全局 `akm-node`,参数透传(`login` 等照常可用);`.sh` 版本额外兼容 Windows 的 `akm-node.exe` 与 `~/.local/bin` 不在 PATH 的情形
  - **踩坑 1(文件编码)**:`.ps1` 必须以 **UTF-8 BOM** 保存。Windows PowerShell 5.1 对无 BOM 文件按系统 ANSI(GBK)解码,中文注释/字符串会被误解码导致**解析失败且无任何输出**。`.sh` 反之不能有 BOM(会破坏 shebang)。仓库既有 `deploy/install-akm-node.ps1` 同样带 BOM,可作为约定佐证。
  - **踩坑 2(错误偏好)**:`& $AkmNode @args` 之前需把 `$ErrorActionPreference` 恢复为 `Continue`——节点运行中会往 stderr 写日志,在 `Stop` 下可能被当作终止性错误中断包装脚本。
  - **验证方式**:`.ps1` 因本机执行策略为 `Restricted`(见 7.7)**无法在会话内实跑**,故采用 ① `Parser::ParseFile` 语法检查(0 错误)② 内联复现判定链(env 文件存在判定、`Get-Command` 未命中后回退绝对路径且该路径存在)。语义由 `.sh` 版端到端验证(§5)。
- [x] 4.2 创建 `~/.akm-node-prod/.env`:Hub 地址(`wss://gotitos.club/akm/ws`)、API 地址、账号、知识库目录(`E:\works-doc`)、独立 `AKM_NODE_ID` 与 `AKM_NODE_NAME`
- [x] 4.3 `cd src/node && uv tool install . --reinstall` 从源码构建独立实例;实测 `site-packages` 内含 `app` 与 `akm_shared`(path 依赖解析正确),可执行文件 `~/.local/bin/akm-node.exe`

## 5. 实机验证(隔离生效)

- [x] 5.1 快照独立:正式实例运行后 `~/.akm-node-prod/sync_state.json` 生成,304 条
- [x] 5.2 互不干扰:正式实例运行后 `~/.akm-node/.env`(md5 `16d654c9…`)与 `~/.akm-node/sync_state.json`(md5 `290f4190…`)与运行前**完全一致**;`src/node/data/` 未被创建
- [x] 5.3 同步正确:Hub 侧该节点(node_id `335d4bab…`)文档数 **304** == 本地快照 304
- [x] 5.4 身份独立:启动日志 `Node: WANG-Work-PC-Prod (windows)`,`AKM_NODE_ID` 显式指定且与开发实例(按机器名自动生成)不同
- [x] 5.5 遗留进程清理:验证结束后无 `akm-node` 残留进程,8000 / 8899 端口无占用

> "双实例并存"只做了静态验证(快照与凭证路径互不相同、正式实例未触碰开发侧文件),
> **未做两个实例同时连同一 Hub 的破坏性实测**——那会让同一份知识库以两个节点身份各推一遍、
> 在 Hub 侧产生重复副本。开发实例按要求连本地 Hub,本机当前未启动本地 Hub。

## 6. 文档与收尾

- [x] 6.1 `docs/env-isolation-design.md`:§2 标注缺陷已修并说明安装版为何"恰好避开";§3 目标形态更新(命令=启动脚本、身份独立);§5 各步骤标注完成并附实测日志;§6 验证表补实测结果;§8 待确认项全部回填结论
- [x] 6.2 `docs/deployment.md` 新增 §2.6「正式 / 开发双环境隔离」:四维隔离表、两个变量的时机陷阱、搭建步骤、验证判据、`AKM_NODE_ID` 互顶 token 的坑
- [x] 6.3 `src/node/.env.example` 新增 §6「多环境隔离」段,说明两个变量 + "为什么必须放启动脚本";`README.md` 配置表补一行 + 指向 deployment §2.6
- [x] 6.4 红线自查(`docs/conventions/workflow.md` §3):无业务领域绑定;未触碰仓外仓库与参考仓;对外契约无变化(纯进程内路径解析);未混入私有部署配置——`~/.akm-node-prod/.env` 位于仓库之外且不入库,`src/node/.env` 亦已被 gitignore

## 7. 遗留

- [ ] 7.1 **归档**:待 `openspec` CLI 可用时执行 `openspec archive 2026-09-30-fix-node-state-isolation --yes`,delta 合入 `openspec/specs/multi-node-sync/`
- [ ] 7.2 `AKM_PROFILE` 式的完整多环境派生(profile → env/state/日志路径一键派生)未实现,见 design.md §3.3
- [ ] 7.3 多实例单机互斥 / 实例锁未实现(当前设计支持多实例并存,不做互斥)
- [ ] 7.4 开发实例的 Hub 切换:当前 `~/.akm-node/.env` 仍指向 `gotitos.club/akm`(node_id `79aec47f…`),计划改指本地 Hub(用户自启)。**两个实例不要同时连同一个 Hub**——会用两个身份把同一份知识库各推一遍
- [ ] 7.5 `uv tool update-shell` 未执行:本机 `~/.local/bin` 不在 PATH,靠启动脚本的绝对路径回退工作;若要直接敲 `akm-node`,需执行一次
- [ ] 7.6 部署在 `gotitos.club/akm` 的 Hub 疑似未更新到含 `origin` 字段的最新 server 代码(实测 `GET /api/documents` 响应中 `origin` 为 `null`),建议核对线上部署版本
- [ ] 7.7 `.ps1` 启动脚本未做本机实跑验证:本机 PowerShell 执行策略为 **`Restricted`**(`Get-ExecutionPolicy` 生效值),任何 `.ps1` 都提示"在此系统上禁止运行脚本"。已做语法检查(0 错误)+ 逻辑内联复现 + `.sh` 版端到端验证;建议在有权限的终端用
      `powershell -ExecutionPolicy Bypass -File deploy\start-node-prod.ps1` 补跑一次确认
