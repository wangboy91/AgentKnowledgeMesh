# CLAUDE.md · 知识基建团队章程

> 本仓属于**基座层**。在此目录启动的会话 = 知识基建团队成员。
> **一切工程规约以 [`AGENTS.md`](AGENTS.md) 为准**(规约地图:UI / 流程 / 文件规范分册在 [`docs/conventions/`](docs/conventions/))。

## 使命

维护 AgentKnowledgeMesh:分布式知识库(Hub+Node)、文档索引与转换、混合检索、Context API、MCP Server。它是上层产品的知识与记忆基座,兼公司内网 wiki。

## 铁律(全文解释见 AGENTS.md 与 docs/conventions/workflow.md)

1. **产品无关**:代码、文档、commit 不得出现具体产品的领域词汇
2. **契约责任**:Context API / MCP / 检索等对外契约,变更先登记 `platform-contracts.md` 再合入
3. **不越界**:不改其他仓库;产品需求走 `platform-request` 任务单
4. **双身份边界**:内网 wiki 与产品组件共用引擎,但内网配置/数据不混入产品交付路径

## 工作流

任务(`company/tasks/` 待领取)→ openspec 变更(new → apply → verify → archive)→ 完成报告 → 红线审计。流程细节见 [docs/conventions/workflow.md](docs/conventions/workflow.md)。

## 语言约定

始终使用中文回答与撰写文档;代码标识符、commit 主题保持简洁(中文可)。
