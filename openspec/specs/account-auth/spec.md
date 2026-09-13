# account-auth 能力规格

# account-auth 能力增量

## Purpose

为 Hub 提供账号与权限管理:两级角色(admin/viewer)的用户账号、登录会话(JWT)、全端点鉴权矩阵,以及 API Token 与节点凭证两类长期凭证的生命周期管理(创建/轮换/吊销)。

## Requirements

### Requirement: 用户账号与角色
系统 SHALL 维护用户账号,含唯一用户名、密码哈希、角色(`admin` 或 `viewer`)与禁用标志;`admin` SHALL 可创建与禁用用户;被禁用账号 SHALL 无法登录。

#### Scenario: 首次启动初始化管理员
- **WHEN** Hub 首次启动且用户表为空
- **THEN** 若配置了 `AKM_ADMIN_USERNAME` / `AKM_ADMIN_PASSWORD` 则按配置创建 admin;否则生成随机密码,将用户名与一次性密码打印到启动日志

#### Scenario: 重复用户名被拒
- **WHEN** admin 创建已存在的用户名
- **THEN** 系统返回 409 冲突错误

### Requirement: 登录与会话
系统 SHALL 提供 `POST /api/auth/login`:校验用户名与密码,签发有效期为 24 小时的 JWT;无效凭证、被禁用账号或过期令牌 SHALL 返回 401。会话密钥 SHALL 支持通过 `AKM_SECRET_KEY` 配置,未配置时首次启动生成并持久化到本地数据目录。

#### Scenario: 正确凭证登录
- **WHEN** 以有效的 admin 或 viewer 凭证调用登录端点
- **THEN** 返回 `access_token`,后续请求以 `Authorization: Bearer <token>` 携带

#### Scenario: 凭证错误或账号禁用
- **WHEN** 用户名不存在、密码错误或账号已被禁用
- **THEN** 返回 401,不区分具体原因

#### Scenario: 令牌过期
- **WHEN** 携带签发超过 24 小时的 JWT 访问受保护端点
- **THEN** 返回 401,客户端需重新登录

### Requirement: 密码修改与恢复
系统 SHALL 提供 `POST /api/auth/change-password` 供登录用户修改本人密码;SHALL 提供 `reset-password` 命令行入口,供管理员在本机重置指定账号密码。

#### Scenario: 修改本人密码
- **WHEN** 登录用户提交旧密码与新密码且旧密码校验通过
- **THEN** 密码更新,之后仅新密码可登录

#### Scenario: 本机重置
- **WHEN** 在 Hub 所在机器执行 reset-password 命令并指定用户名
- **THEN** 交互输入并设置新密码,无需登录

### Requirement: 端点鉴权矩阵
除 `GET /api/health` 与登录端点外,全部 `/api` 端点 SHALL 要求有效 Bearer 凭证(JWT、API Token 或节点 token 三选一);**读操作(GET)**对 admin、viewer 及节点 token 放行,**写操作**(POST/PUT/DELETE)SHALL 仅限 admin;用户管理与 API Token 管理 SHALL 仅限 admin。凭证无效或缺失 SHALL 返回 401,角色不足 SHALL 返回 403。

#### Scenario: 未认证访问被拒
- **WHEN** 不携带凭证调用 `GET /api/documents`
- **THEN** 返回 401

#### Scenario: viewer 只读
- **WHEN** viewer 调用 `POST /api/documents/scan`
- **THEN** 返回 403;同一用户调用 `GET /api/search` 正常返回

#### Scenario: 节点凭证只读
- **WHEN** 以节点 token 调用 `GET /api/search`
- **THEN** 正常返回;同一 token 调用 `DELETE /api/nodes/{id}` 返回 403

#### Scenario: 鉴权豁免清单
- **WHEN** 未携带凭证调用 `GET /api/health` 或 `POST /api/auth/login`
- **THEN** 正常响应

### Requirement: API Token 管理
系统 SHALL 支持管理员创建、列出与吊销 API Token:创建时生成一次性明文并仅在该次响应返回,存储端只保存哈希;列表仅展示名称、前缀与状态;吊销后该 token 立即失效。

#### Scenario: 创建返回明文一次
- **WHEN** admin 创建名为 "ci-agent" 的 API Token
- **THEN** 响应包含完整明文 token,此后任何列表查询都不再返回明文

#### Scenario: 吊销立即生效
- **WHEN** admin 吊销某 API Token 后,凭该 token 调用 `GET /api/context`
- **THEN** 返回 401

### Requirement: 节点凭证获取与生命周期
系统 SHALL 提供 `POST /api/nodes/register`(admin JWT 鉴权):携带节点名与平台信息,创建或更新节点记录并**轮换生成**新节点 token 返回;Web 端 SHALL 支持对节点执行重置 token(轮换,旧 token 立即失效)与禁用(该节点全部请求被拒)操作。

#### Scenario: CLI 登录换取节点 token
- **WHEN** 节点机执行 `akm-node login`,输入 Hub 地址与管理员凭证
- **THEN** 节点调用注册端点,获得 `node_id` 与节点 token 并写入本地配置;此后启动无需交互

#### Scenario: 重置 token 后旧凭证失效
- **WHEN** admin 在 Web 端对某节点执行重置 token
- **THEN** 该节点旧 token 的注册与上传请求返回 401,使用新 token 恢复正常

#### Scenario: 禁用节点
- **WHEN** admin 禁用某节点后,该节点以原 token 连接
- **THEN** 注册被拒(4001)、文档上传返回 401
