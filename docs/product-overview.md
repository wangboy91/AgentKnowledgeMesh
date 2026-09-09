# 产品概要 · AgentKnowledgeMesh

> 面向 AI Agent 时代的分布式知识库:把散落在各台电脑上的 Markdown 文档、Agent 记忆、项目资料,汇成一个可检索的知识网络,并经 MCP / Context API 供智能体直接取用。

## 1. 定位与价值

| 维度 | 说明 |
| --- | --- |
| 产品定位 | 分布式知识库(Hub + Node);上层产品的知识与记忆基座,兼公司内网 wiki |
| 目标用户 | ① 个人:统一管理本地 Markdown;② 团队:内网共享知识、分级查阅;③ AI Agent:经 MCP / Context API 检索 |
| 核心价值 | 多机汇聚、统一检索(关键词 ⊕ 语义混合)、Agent 标准接入(MCP)、轻量部署(SQLite / PostgreSQL) |

## 2. 角色与权限愿景

| 角色 | 载体 | 能力 | 引入版本 |
| --- | --- | --- | --- |
| admin | Web 登录账号 | 全部读写:文档、节点、用户管理、RAG 模式、token 吊销 | V0.4 |
| viewer | Web 登录账号 | 只读:浏览、搜索、查阅文档与节点状态 | V0.4 |
| node | CLI 登录的机器身份 | 向 Hub 推送本地文档、心跳保活 | V0.4(登录化) |
| agent | API Token(长期凭证) | 经 Context API / MCP SSE 检索 | V0.4(凭证化) |

## 3. 功能地图

### 已交付(V0.1 – V0.3)

- 本地 Markdown 递归扫描与增量索引(hash 识别变更)
- 关键词搜索 + 语义检索(混合检索:dense ⊕ sparse,RRF 融合,Markdown 感知分块)
- Hub + Node 多节点架构:WebSocket 注册/心跳、HTTP 文档上传、节点文档向量同步
- Web 界面:文档浏览(Markdown 渲染)、在线编辑、暗色/亮色主题、可拖侧边栏
- Context API(`/api/context`)、MCP Server(stdio + SSE)
- 文档转换(PDF / Word / HTML / URL → Markdown)

### 本批规划(V0.4 · 账号与治理)

| # | 主题 | 解决的问题 | 详细设计 |
| --- | --- | --- | --- |
| 1 | 账号与鉴权体系 | Web 读写全裸奔;token 无生命周期 | [technical-design.md §2](technical-design.md) |
| 2 | 节点 CLI 登录接入 | 节点匿名注册,token 无法吊销/轮换 | [technical-design.md §3](technical-design.md) |
| 3 | hash-first 节点同步 | 每次同步全量推送,流量 O(全部字节) | [technical-design.md §4](technical-design.md) |
| 4 | RAG 同步模式(auto/manual + 文档级勾选) | 无法控制"哪些文档进向量库" | [technical-design.md §5](technical-design.md) |
| 5 | Web 中英文切换 | 界面文案硬编码中文 | [technical-design.md §6](technical-design.md) |
| 6 | 知识库三栏树形浏览 | 无法按节点浏览目录、文档扁平展示 | [technical-design.md §7](technical-design.md) |
| 7 | Node 本地 MCP 代理 | 智能体需逐个配置 Hub 地址/凭证 | [technical-design.md §9](technical-design.md) |

> 待定项:Hub 静态托管目录统一(环境变量化)—— 现状与候选方案见 [technical-design.md §8](technical-design.md),想清楚后再实施。

### 远期(V1.0+)

- 知识图谱(实体/关系抽取与图检索)
- 检索质量评测自动化(纳入 CI)
- 节点端到端加密同步

## 4. 迭代计划

| 版本 | 主题 | 内容 | 状态 |
| --- | --- | --- | --- |
| V0.1 | 单机知识库 | 扫描索引、Web 浏览、关键词搜索、Docker 部署 | ✅ |
| V0.2 | 多节点架构 | Hub+Node、WebSocket、注册心跳、远程文档 | ✅ |
| V0.3 | Agent 集成 | Context API、MCP、混合检索(RAG)、文档转换、在线编辑 | ✅ |
| V0.4 | 账号与治理 | 上表 6 项:账号鉴权、CLI 接入、增量同步、RAG 模式、i18n、三栏树 | 🚧 进行中 |
| V1.0 | 智能化 | 知识图谱、评测自动化 | ⏳ 规划 |

## 5. 本批验收口径

1. 未登录访问任意 API(除 health/auth)→ 401;viewer 执行写操作 → 403
2. 节点机一条命令 `akm-node login` 完成接入;Web 端可吊销/重置该节点 token,吊销后节点同步被拒
3. 大知识库二次同步的上行流量 ≈ 变更量,而非全量字节
4. manual 模式下,只有被勾选的文档出现在语义检索结果中;auto 模式行为与 V0.3 一致
5. 界面无硬编码文案,中英文一键切换并持久记忆
6. 知识库页:选节点 → 目录树(默认收起)→ 点开文档即渲染
