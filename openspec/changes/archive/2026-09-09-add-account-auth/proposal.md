# Proposal: add-account-auth

## Why

当前全部 Web API 无鉴权(仅节点上传端点校验 Bearer token),任何能访问 Hub 的人都能读写全部知识;节点 token 注册即发、永久复用,无吊销/轮换手段,泄漏后无法止损。知识库作为上层产品与内网 wiki 的基座,读写必须纳入账号与权限管理。

## What Changes

- 新增用户账号体系:`users` 表(id、用户名唯一、密码哈希、role、disabled),`admin` / `viewer` 两级角色
- 新增登录端点与 JWT 会话(24h);**BREAKING** 除 `GET /api/health` 与登录端点外,全部 `/api` 端点要求 Bearer 凭证;viewer 只读、admin 可写(修复读/写鉴权不对称)
- 新增管理员初始化:首次启动从 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` 创建,未配置则生成随机密码打印一次;提供 `reset-password` 恢复命令
- 新增 API Token 管理(admin 创建/列出/吊销,仅创建时返回明文),供 Agent/脚本调用 Context API 与 MCP SSE
- 节点接入改登录制:**BREAKING** 匿名 WS 注册被拒;新增 `akm-node login`(交互输入 Hub 地址与管理员账号密码)→ `POST /api/nodes/register` 换取节点 token → 写入节点本地 `.env`
- 节点 token 生命周期:Web 端可重置(轮换,旧 token 失效)与禁用;节点凭证获得**只读**知识端点权限(search / rag/search / context / documents 读取类),供节点本地 MCP 代理使用
- Web 端新增登录页、401/403 统一处理、登出;viewer 角色隐藏写操作入口

## Capabilities

### New Capabilities

- `account-auth`: 用户账号与两级角色、登录会话(JWT)、端点鉴权矩阵、API Token 与节点凭证的生命周期管理

### Modified Capabilities

- `multi-node-sync`: WS 注册必须携带节点 token(匿名注册被拒);节点令牌改由 CLI 登录流颁发/轮换,注册时校验

## Impact

- **server**:新增 auth 领域(users / api_tokens 模型、密码哈希、JWT、统一鉴权依赖);documents / search / nodes / rag / context / mcp 全部路由注入鉴权;websocket 注册校验改造
- **node**:新增 `login` 子命令与本地凭证存储(`.env`);启动注册携带 token
- **web**:登录页、请求层鉴权头与 401/403 处理、按角色隐藏写入口、节点管理页新增 token 重置/禁用
- **依赖**:新增密码哈希与 JWT 库(见 design)
- **契约**:Context API / MCP SSE 新增鉴权要求,已同步 `docs/api-reference.md`(对外契约以本仓文档为准)
- **兼容**:已部署的旧节点升级后须执行 `akm-node login` 重新接入;使用 Context API / MCP 的智能体须改配 API Token
