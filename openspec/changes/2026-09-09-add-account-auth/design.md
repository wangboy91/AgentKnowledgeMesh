# Design: add-account-auth

## Context

现状:全部 REST 端点无鉴权(仅 `PUT /api/nodes/{id}/documents` 校验 Bearer);节点 WS 连上即注册,token 为 `uuid4().hex` 注册时首签、永久复用。web 端 `client.ts` 为唯一请求出口,`api/__init__.py` 聚合路由。技术方案详见 [docs/technical-design.md](../../../docs/technical-design.md) §2、§3、§9。

## Goals / Non-Goals

**Goals:**
- 全端点鉴权(401/403 语义清晰),admin/viewer 两级角色
- JWT 会话 + API Token + 节点 token 三类凭证统一解析
- 节点 CLI 登录接入与 token 轮换/禁用
- 向后兼容的过渡路径(API Token 供既有集成迁移)

**Non-Goals:**
- 多租户、细粒度权限矩阵、SSO/OAuth(P1 不做,role 字段预留扩展)
- JWT 刷新机制(24h 过期重登)
- 节点 token 自动过期(仅轮换/禁用)

## Decisions

1. **密码哈希用 `passlib[bcrypt]`**。备选:`hashlib.pbkdf2_hmac` 自实现(无新依赖,但轮 iterations/格式管理自己担)。若 bcrypt 依赖在目标环境安装受阻,降级 pbkdf2,接口不变(`hash_password` / `verify_password` 两函数隔离)。
2. **会话用 JWT(HS256,`pyjwt`)**,密钥 `AKM_SECRET_KEY` 未配置时首启生成 32 字节随机值存 `data/secret.key`(0600)。备选:服务端 session 表(每请求查库,弃)。
3. **统一凭证解析依赖** `resolve_principal`:按序识别 JWT(用户)/ API Token(哈希比对)/ 节点 token(仅 `PUT /api/nodes/{id}/documents`、只读知识端点白名单与 WS 注册),返回 `(principal_type, role)`;各路由用 `require_auth(min_role)` 包装。避免每路由自行解析。
4. **node token 沿用 `nodes.token` 字段**,不另建表;重置 = 覆盖该字段,禁用 = `status="disabled"`(与在线状态 online/offline 解耦,新增字段 `disabled` bool 更清晰,选后者)。
5. **匿名注册直接拒绝(BREAKING)**:无灰度开关 —— 当前部署面小(单机/内网),保留开关反而留下裸奔路径。
6. **admin 初始化放 lifespan**(建表后、端口监听前);随机密码打印使用 stdout(入口已 reconfigure UTF-8,编码安全)。

## Risks / Trade-offs

- [既有 MCP/Context 集成全断] → API Token 先行:发布说明引导生成 token 替换;`platform-contracts.md` 登记新鉴权要求
- [JWT 泄漏] → 24h 短有效期;生产部署建议 HTTPS(文档说明)
- [忘记 admin 密码] → `reset-password` 本机命令兜底
- [全端点上锁后测试面扩大] → 鉴权矩阵参数化测试逐组覆盖(见 tasks)

## Migration Plan

1. 设 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` → 启动新版 Hub(users 表由 `create_all` 自动创建)
2. 登录生成 API Token,替换既有智能体的 Context API / MCP SSE 配置
3. 各节点机执行 `akm-node login` 重新接入
4. 回滚:回退镜像/代码即可,数据无破坏性迁移(仅新增表与字段)

## Open Questions

无(密码哈希库的最终选型在实现时按安装情况二选一,接口已隔离,不影响工件)。
