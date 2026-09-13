# CLAUDE.md · AgentKnowledgeMesh 项目章程

> 本仓是一个**独立项目**:面向 AI Agent 时代的分布式知识库。
> **一切工程规约以 [`AGENTS.md`](AGENTS.md) 为准**(规约地图:UI / 流程 / 文件规范分册在 [`docs/conventions/`](docs/conventions/))。

## 使命

维护 AgentKnowledgeMesh:文档索引与转换、关键词⊕语义混合检索、Context API、MCP Server、多节点知识同步。可独立部署为团队/企业内网知识库,也可作为知识组件被上层应用集成。

## 铁律

1. **产品无关**:代码、文档、commit 不绑定任何具体业务领域,保持通用知识能力
2. **契约责任**:对外契约(REST / WS / MCP / Context API)变更须同步 `docs/api-reference.md` 与 openspec 增量,并评估向后兼容
3. **不越界**:不修改本仓之外的任何仓库
4. **双身份边界**:作为内网知识库部署产生的私有配置/数据,不混入产品交付路径(文档、示例、默认值)

## 工作流

需求(用户直接下达 / 自主迭代)→ openspec 变更(new → apply → verify → archive)→ 完成报告。流程细节见 [docs/conventions/workflow.md](docs/conventions/workflow.md)。

## 语言约定

始终使用中文回答与撰写文档;代码标识符保持英文。
