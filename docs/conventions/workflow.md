# 流程规范 · 开发与协作

> 适用范围:本仓全部变更(代码、文档、openspec 工件)。规约地图见根目录 `AGENTS.md`。

## 1. 任务来源

本项目为**独立项目**,需求不经过外部任务单:

- 用户直接下达的需求(主要来源)
- 自主迭代:问题/改进先在 `docs/` 层面说清楚(产品/技术文档),再按 §2 分流决定是开 openspec 变更还是直接改

## 2. 变更分流与 openspec 生命周期

**先分流:openspec 只覆盖"修改代码实施"的改动** —— 即会改变程序行为或对外能力的变更。不改变代码行为的改动**直接改**,不新建变更目录(为几行配置开一份 proposal/design/tasks/spec 是空转)。

| 走 openspec(代码实施) | 直接改(编排 / 配置 / 文档) |
| --- | --- |
| `src/{server,node,web,shared}` 源码的行为变更 | `deploy/` 部署编排(compose)、安装脚本 |
| 对外契约(REST / WS / MCP / Context API)变更 | `Dockerfile` / 构建参数、`src/Makefile` 等构建入口 |
| 新增/移除能力(含 spec 级要求) | 配置对齐、重复文件清理、目录/命名规整 |
| 数据结构、协议、鉴权等有兼容性影响的改动 | 文档修正与补充(README / docs/) |

- 两类混在一起时**拆开**:代码部分走 openspec,编排/文档部分直接改并随当次提交说明
- 拿不准是否影响代码行为:按"会影响"处理(开变更),或先问一句
- 直接改的改动同样要过验证基线(§4)与红线自查(§3),只是不写工件

走 openspec 时按下面生命周期执行:

```
new change → (proposal / design / tasks / specs) → apply → verify → archive
```

1. **new**:变更目录 `openspec/changes/YYYY-MM-DD-<add|fix>-<名称>/`,工件沿用既有 spec 的中文写法
2. **apply**:按 tasks.md 逐项实现,完成一项勾一项;每个 task 可独立验证
3. **verify**:实现与工件一致;`openspec` 校验 + 验证基线(§4)全绿
4. **archive**:归档到 `openspec/changes/archive/`,delta specs 合入 `openspec/specs/`

## 3. 完成回报

- 完成后在任务/变更上下文中给出完成报告(改动清单、验证结果、遗留项)
- 红线自查清单(每变更一次):
  - [ ] 代码/文档/commit 不绑定具体业务领域(保持通用知识能力)
  - [ ] 未修改本仓之外的任何仓库;未触碰参考仓(`deepseek-harness/`、`BossHunter/`)
  - [ ] 对外契约(端点/协议/MCP)变更已同步 `docs/api-reference.md` 并评估向后兼容
  - [ ] 私有部署产生的配置/数据未混入产品交付路径(文档、示例、默认值)

## 4. 验证基线(每变更提交前)

```bash
cd src/server && uv run pytest          # 单测全绿
cd src/web    && npm run build          # 前端可构建
# API 冒烟(hub 运行中):health / stats / scan / search / rag/stats
```

涉及节点/WS 的变更:另起 Hub+Node 手测注册→心跳→同步链路(参考 `docs/technical-design.md` §9)。

> **AI 会话附加规约**:需要用户测试/调试时,服务由**用户自己启动**(AI 只给命令,不代启、不占端口);AI 自动启动的服务仅限自身自动化验证,验证完成立即关闭,收尾前自查无本会话遗留的运行中进程。

## 5. 分支与提交

- **提交由用户本人执行:AI 会话(无论何种工具/模式)不执行 `git commit` / `git push`**,完成后将变更留在工作区并列出改动清单
- 提交信息:中文、一行主题(可加正文);主题 = 本次变更做的事,不写"完成阶段任务"这类空话
- 一个变更一个主题;修复与功能分开提交
- 不强推(force-push)共享分支;敏感信息(`.env`、token)永不入库

## 6. 文档更新义务

- 行为变化 → 同步更新 `README.md`(用户视角)与 `AGENTS.md`(工程视角)
- 架构/接口决策 → `docs/technical-design.md` 或 openspec design;对外契约变化 → `docs/api-reference.md` 同步
