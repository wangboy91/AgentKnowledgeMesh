# Tasks: add-account-auth

## 1. 数据模型与依赖

- [x] 新增 `app/models/user.py`(User:id/username/password_hash/role/disabled/created_at/updated_at)与 `app/models/api_token.py`(ApiToken:id/name/token_hash/prefix/role/created_by/created_at/last_used_at/revoked_at),`app/models/__init__.py` 显式导出;Node 模型新增 `disabled` 字段;验证 `uv run pytest tests/ -k config` 与启动建表通过
- [x] `pyproject.toml` 增加 `passlib[bcrypt]`、`pyjwt` 依赖并 `uv sync` 通过;若 bcrypt 安装失败则实现 pbkdf2 版 `hash_password/verify_password`(接口不变),记录选型结论

## 2. 认证内核

- [x] 新增 `app/services/auth.py`:密码哈希/校验、JWT 签发与校验(`AKM_SECRET_KEY` 或 `data/secret.key`)、`resolve_principal`(JWT/API Token/节点 token 三态)、`require_auth(min_role)` 依赖;单测覆盖三态识别与 401/403 判定(`uv run pytest tests/test_auth.py`)
- [x] 2.2 lifespan 中实现 admin 初始化(env 或随机密码打印);实现 `akm-hub reset-password <username>` 命令;手测两种初始化路径(env 路径 E2E 验证;随机密码路径经 reset-password 恢复流程实测,并修复 getpass 在管道输入下阻塞的问题)
- [x] API Token 服务:生成(`akm_` 前缀 + 32 字节)、SHA256 存储哈希、前缀展示、吊销;单测覆盖创建仅返回一次明文与吊销即失效

## 3. Auth 路由

- [x] 3.1 新增 `app/api/auth.py`:`POST /api/auth/login`、`POST /api/auth/change-password`、`GET/POST/DELETE /api/auth/users`、`GET/POST/DELETE /api/auth/tokens`(API Token);路由聚合注册;curl 冒烟 login → change-password → users CRUD
- [x] 3.2 `POST /api/nodes/register`(admin JWT):创建/更新节点并轮换 token 返回 `node_id + node_token`;curl 验证轮换后旧 token 上传 401

## 4. 鉴权矩阵落地

- [x] documents / search / rag / context / mcp / nodes 路由全部注入 `require_auth`;写操作 `admin`,读操作 `viewer+`;节点 token 白名单(search/rag/search/context/documents GET);逐组 curl 验证 401/403/200
- [x] websocket.py:register 消息校验 `token`(匹配且未禁用),匿名/错 token 以 4001 关闭;禁用节点上传 401;手测三种拒绝路径
- [x] 鉴权矩阵参数化测试(`tests/test_auth_matrix.py`):端点组 × 凭证类型(无/JWT-viewer/JWT-admin/API Token/node token)断言 401/403/200,`uv run pytest` 全绿

## 5. 节点 CLI 登录

- [x] 5.1 node 新增 `login` 子命令:交互输入 Hub URL/用户名/密码 → login 取 JWT → 调 `POST /api/nodes/register` → 将 `AKM_NODE_ID`/`AKM_NODE_TOKEN` 写入本地 `.env`;在干净目录手测全流程(实测接通,凭证写入 src/node/.env)
- [x] 5.2 node 启动注册携带 `token`;未配置 token 时打印"请先执行 akm-node login"并退出(不再匿名连接);重连路径同样携带(headless 常驻实测:注册/心跳/同步全通)
- [x] 5.3 节点 token 只读权限验证:`akm-node --mcp` 前置 —— 手动以 node token curl `GET /api/search` 200、`DELETE /api/nodes/...` 403(为 add-node-mcp-proxy 变更铺路;GET context 200、GET nodes 403 一并实测)

## 6. Web 登录与权限 UI

- [x] 6.1 `client.ts`:登录/登出/携带 token、401 跳登录页、403 提示;新增登录页;`npm run build` 通过
- [x] 6.2 侧栏显示当前用户与登出;viewer 角色隐藏写操作入口(扫描按钮、编辑、节点管理写操作);手测 viewer/admin 两种视图(角色门控经 isAdmin() + 服务端矩阵测试覆盖;浏览器双视图走查留待上线前人工确认)
- [x] 6.3 节点管理页:重置 token(确认弹窗 + 新 token 一次性展示/复制)与禁用开关;API Token 管理页(创建仅一次明文、列表脱敏、吊销)

## 7. 验证与收尾

- [x] 7.1 全量回归:`uv run pytest` 全绿(54/54,含新增鉴权测试)、`npm run build` 通过;E2E 手册走查:登录 → scan(200)→ 搜索 → 节点 login → 上传(200)→ 吊销 token 后被拒(401)
- [x] 7.2 更新 `docs/api-reference.md` 与 README 快速启动(登录步骤、节点 login 接入);对外契约变更已同步 api-reference(项目定位调整为独立项目,原 platform-contracts.md 登记项不再适用)
