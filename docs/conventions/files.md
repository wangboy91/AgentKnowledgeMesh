# 文件规范 · 目录与命名

> 适用范围:本仓全部文件。规约地图见根目录 `AGENTS.md`。

## 1. 顶层目录

```
AgentKnowledgeMesh/
├── src/
│   ├── server/        # Hub 后端(FastAPI);入口 uv run akm-hub
│   ├── node/          # Node 客户端;入口 uv run akm-node
│   ├── web/           # 前端(React+Vite+TS);构建产物 dist/(不入库)
│   └── shared/        # 共享扫描器(akm-shared,本地 path 依赖)
├── docs/              # 产品与技术文档 + 规约(见 §3)
├── deploy/            # 发版/部署资产:安装脚本、部署 compose、本地构建脚本
├── openspec/          # 规范驱动开发工件(specs/ 与 changes/)
├── AGENTS.md          # 工程规约地图(会话/开发者入口)
├── CLAUDE.md          # 团队章程(薄,指向 AGENTS.md)
└── README.md          # 项目说明(用户视角)
```

- `src/server/data/`(数据库)、`src/server/.env`、各 `.venv`、`dist/`、`node_modules/`:生成物/本地配置,**不入库**
- 根目录不放代码;新目录先进 `docs/` 或 `src/` 讨论定位
- 脚本按类型进 `<module>/tests/`、`<module>/scripts/`、`<module>/eval/`,模块根目录禁放散装脚本(见 [scripts.md](scripts.md))

## 2. 命名

| 对象 | 约定 | 示例 |
| --- | --- | --- |
| Python 模块/函数/变量 | snake_case | `sync_node_documents` |
| Python 类 | PascalCase | `ConnectionManager` |
| React 组件/文件 | PascalCase.tsx | `FileTree.tsx` |
| 前端普通模块 | camelCase.ts | `client.ts` |
| 环境变量 | `AKM_` 前缀 + 大写下划线 | `AKM_KNOWLEDGE_ROOTS` |
| openspec 变更目录 | `YYYY-MM-DD-<add\|fix>-<英文短名>` | `2026-09-09-add-account-auth` |
| API 路径 | 复数名词 + kebab-case 动作 | `/api/documents/rag/batch` |

## 3. docs/ 结构

```
docs/
├── product-overview.md    # 产品概要:定位/角色/功能地图/迭代计划
├── technical-design.md    # 技术方案:当前批次的架构与接口设计
├── api-reference.md       # API 参考(全部端点)
├── deployment.md          # 部署指南(Hub 容器 / akm-node 一键安装)
└── conventions/
    ├── ui.md              # UI 规范(布局/主题/i18n/交互)
    ├── workflow.md        # 流程规范(openspec 生命周期/验证基线)
    ├── scripts.md         # 脚本规范(测试/调试脚本的存放与注释)
    └── files.md           # 本文件(目录/命名/职责)
```

新增文档先在本文 §3 登记;放不进现有分类的,先讨论再建目录。

## 4. 代码职责边界

| 层 | 只做 | 不做 |
| --- | --- | --- |
| `server/app/api/` | 路由编排、入参出参、鉴权注入 | 业务逻辑(下沉 services) |
| `server/app/services/` | 业务逻辑;rag 子域专管向量化/检索 | 直接定义路由 |
| `server/app/models/` | ORM 模型与 to_dict | 跨模型业务 |
| `node/app/` | 扫描、同步、WS 客户端 | 任何服务端职责 |
| `web/src/api/client.ts` | 唯一请求出口(鉴权头、错误归一) | UI 逻辑 |

## 5. 禁止修改清单

- 他人提交的 openspec 归档(`openspec/changes/archive/`)—— 修历史用新变更
- 生成物:`dist/`、`.venv/`、`data/*.db`
