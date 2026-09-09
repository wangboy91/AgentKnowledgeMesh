# 流程规范 · 开发与协作

> 适用范围:本仓全部变更(代码、文档、openspec 工件)。规约地图见根目录 `AGENTS.md`。

## 1. 任务来源

- 上级任务单:`company/tasks/` 中接收团队为"知识基建团队"的任务单
- 仓内自发改进:先在 `docs/` 层面说清楚(产品/技术文档),再开 openspec 变更

## 2. openspec 变更生命周期

```
new change → (proposal / design / tasks / specs) → apply → verify → archive
```

1. **new**:变更目录 `openspec/changes/YYYY-MM-DD-<add|fix>-<名称>/`,工件沿用既有 spec 的中文写法
2. **apply**:按 tasks.md 逐项实现,完成一项勾一项;每个 task 可独立验证
3. **verify**:实现与工件一致;`openspec` 校验 + 验证基线(§4)全绿
4. **archive**:归档到 `openspec/changes/archive/`,delta specs 合入 `openspec/specs/`

## 3. 完成回报

- 任务单(如来自 `company/tasks/`)追加完成报告,等待红线审计
- 红线自查清单(每变更一次):
  - [ ] 代码/文档/commit 无具体产品领域词汇(知识层是通用能力)
  - [ ] 未修改其他仓库;未触碰参考仓(`deepseek-harness/`、`BossHunter/`)
  - [ ] 对外契约(Context API / MCP / 检索)变更已先在 `platform-contracts.md` 登记
  - [ ] 内网 wiki 用途的配置/数据未混入产品交付路径

## 4. 验证基线(每变更提交前)

```bash
cd src/server && uv run pytest          # 单测全绿
cd src/web    && npm run build          # 前端可构建
# API 冒烟(hub 运行中):health / stats / scan / search / rag/stats
```

涉及节点/WS 的变更:另起 Hub+Node 手测注册→心跳→同步链路(参考 `docs/technical-design.md` §9)。

## 5. 分支与提交

- 提交信息:中文、一行主题(可加正文);主题 = 本次变更做的事,不写"完成阶段任务"这类空话
- 一个变更一个主题;修复与功能分开提交
- 不强推(force-push)共享分支;敏感信息(`.env`、token)永不入库

## 6. 文档更新义务

- 行为变化 → 同步更新 `README.md`(用户视角)与 `AGENTS.md`(工程视角)
- 架构/接口决策 → `docs/technical-design.md` 或 openspec design;契约变化 → `platform-contracts.md` 登记
