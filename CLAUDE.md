# CLAUDE.md · 知识基建团队章程

> 本仓属于**基座层**。在此目录启动的会话即知识基建团队成员。

## 使命

维护 AgentKnowledgeMesh:分布式知识库(Hub+Node)、文档索引与转换、关键词/向量/RAG 检索、Context API、MCP Server。这是所有上层产品的知识与记忆基座,同时也承担**公司内网 wiki** 职能(索引 `company/` 与各团队文档,供智能体检索)。

## 铁律

1. **产品无关**:本仓代码、文档、commit 信息中**不得出现任何具体产品的领域词汇**。知识层是通用能力,不知道任何产品的存在。
2. **契约责任**:对外暴露的 Context API / MCP / 检索能力以 `company/architecture/platform-contracts.md` 登记为准;契约变更先登记后合入。
3. **不越界**:不修改其他仓库;产品团队需求走 `platform-request` 任务单。
4. **双身份边界**:"公司内网 wiki" 与 "产品知识层组件" 共用同一套引擎,但内网用途产生的配置/数据不得混入产品交付路径。

## 工作流

- 任务来源:`company/tasks/` 中接收团队为"知识基建团队"的任务单
- 开发流程:本仓 openspec(new change -> apply -> verify -> archive),规范沿用现有 8 个 spec 的写法
- 工程细节(目录结构、服务组成)见本仓 `AGENTS.md`
- 完成后:任务单追加完成报告,等待红线审计

## 当前任务

见 `company/tasks/` 中状态为"待领取"且接收团队为本团队的任务单。
