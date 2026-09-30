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
除 `GET /api/health` 与登录端点外,全部 `/api` 端点 SHALL 要求有效 Bearer 凭证(JWT、API Token 或节点 token 三选一);**读操作(GET)**对 admin、viewer 及节点 token 放行;**写操作**(POST/PUT/DELETE)SHALL 仅限 admin,**但文档写端点**(`POST /api/documents` 创建、`PUT /api/documents/{doc_id}` 更新)对节点凭证放行且**作用域限该节点名下文档**——节点凭证创建的文档归属该节点,仅能更新 `node_id` 等于该节点的文档;用户管理与 API Token 管理 SHALL 仅限 admin。凭证无效或缺失 SHALL 返回 401,角色不足 SHALL 返回 403,跨作用域写入 SHALL 返回 403。

#### Scenario: 未认证访问被拒
- **WHEN** 不携带凭证调用 `GET /api/documents`
- **THEN** 返回 401

#### Scenario: viewer 只读
- **WHEN** viewer 调用 `POST /api/documents/scan`
- **THEN** 返回 403;同一用户调用 `GET /api/search` 正常返回

#### Scenario: 节点凭证只读
- **WHEN** 以节点 token 调用 `GET /api/search`
- **THEN** 正常返回;同一 token 调用 `POST /api/documents/scan` 或 `DELETE /api/nodes/{id}` 返回 403

#### Scenario: 节点凭证可写本节点文档
- **WHEN** 以节点 token 调用 `POST /api/documents` 或 `PUT /api/documents/{doc_id}`(目标文档归属该节点)
- **THEN** 放行;创建时 `node_id` 强制为该节点

#### Scenario: 节点凭证跨作用域写入被拒
- **WHEN** 以节点 token 更新归属其他节点或 `local` 的文档
- **THEN** 返回 403

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
系统 SHALL 提供 `POST /api/nodes/register`(admin JWT 鉴权):携带节点名与平台信息,创建或更新节点记录并**轮换生成**新节点 token 返回;Web 端 SHALL 支持对节点执行重置 token(轮换,旧 token 立即失效)与禁用(该节点全部请求被拒)操作。`akm-node login` 成功换取凭证后 SHALL **自动进入运行循环**(连接 Hub → 注册 → 初始扫描同步 → 常驻),不得以直接退出结束登录流程。

#### Scenario: CLI 登录换取节点 token
- **WHEN** 节点机执行 `akm-node login`,输入 Hub 地址与管理员凭证
- **THEN** 节点调用注册端点,获得 `node_id` 与节点 token 并写入本地配置;此后启动无需交互

#### Scenario: 登录成功后自动接入并同步
- **WHEN** `akm-node login` 成功换取并写入凭证
- **THEN** 进程不退出,自动连接 Hub 完成注册,执行初始扫描同步,随后进入常驻运行;用户以 Ctrl+C 退出

#### Scenario: 重置 token 后旧凭证失效
- **WHEN** admin 在 Web 端对某节点执行重置 token
- **THEN** 该节点旧 token 的注册与上传请求返回 401,使用新 token 恢复正常

#### Scenario: 禁用节点
- **WHEN** admin 禁用某节点后,该节点以原 token 连接
- **THEN** 注册被拒(4001)、文档上传返回 401

### Requirement: 节点 CLI 帮助
节点 CLI SHALL 提供 `--help` / `-h` 输出:列出全部命令与用法(`login`、默认运行、`--mcp`、`--version`),并说明断开方式(Ctrl+C)与断线自动重连(默认 5 秒间隔)行为;帮助输出后 SHALL 以退出码 0 结束,不启动客户端。

#### Scenario: 查看帮助
- **WHEN** 执行 `akm-node --help` 或 `akm-node -h`
- **THEN** 输出命令列表、断开方式与断线重连说明,进程以退出码 0 结束

#### Scenario: 帮助优先于其他行为
- **WHEN** 携带 `--help` 的命令行同时包含其他参数
- **THEN** 仅输出帮助并退出,不触发登录或客户端启动

### Requirement: 节点环境变量凭证与启动自动登录

节点 SHALL 支持通过配置项 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 提供 Hub 登录账号。当启动时**不存在**节点凭证(`AKM_NODE_TOKEN` 为空)且上述两个配置项**均非空**时,节点 SHALL 以**非交互**方式调用 `POST /api/auth/login` 与 `POST /api/nodes/register` 换取节点凭证并继续运行(不读取 stdin、不要求 tty);当已存在节点凭证时 SHALL 直接使用该凭证,**不得**调用登录与注册端点。自动登录成功后 SHALL 尽力将 `node_id` / `node_token` 写回用户级 `.env`,写回失败 SHALL 仅告警、不得阻断本次运行。两个配置项未同时提供且无节点凭证时,节点 SHALL 输出引导信息(执行 `akm-node login` 或配置上述变量)并以非零退出码结束,不发起连接。`akm-node login` 交互登录入口 SHALL 保持可用且行为不变。运行中凭证失效时的重登行为 SHALL 保持既有语义(交互终端询问现场重登,非交互保持重试),本能力不引入静默自动重登。

#### Scenario: 配置账号后无凭证启动自动接入
- **WHEN** 节点配置了 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 且本地无节点凭证,执行 `akm-node`
- **THEN** 节点非交互换取节点凭证(不读取 stdin),自动连接 Hub 完成注册并执行首次扫描同步,随后常驻运行

#### Scenario: 已有凭证时不重复登录
- **WHEN** 本地已有 `AKM_NODE_TOKEN` 且同时配置了 Hub 账号,执行 `akm-node`
- **THEN** 直接以现有凭证连接,不调用登录与注册端点(不轮换 token)

#### Scenario: 自动登录失败
- **WHEN** 配置的 Hub 账号或密码错误,节点无凭证启动
- **THEN** 输出登录失败原因,进程以非零退出码结束,不进入运行循环

#### Scenario: 凭证失效后的重登行为不变
- **WHEN** 节点运行中因 token 被重置导致注册被拒,且配置了 Hub 账号
- **THEN** 节点不静默自动重登:交互终端下询问是否现场重登,非交互环境下保持既有重试循环(禁用/重置的治理意图不被无人值守进程自动解除)

#### Scenario: 未配置账号且无凭证
- **WHEN** 未配置 `AKM_HUB_USERNAME` / `AKM_HUB_PASSWORD` 且本地无节点凭证,执行 `akm-node`
- **THEN** 输出引导执行 `akm-node login` 或配置环境变量的提示,进程以非零退出码结束,不发起连接

#### Scenario: 交互登录仍然可用
- **WHEN** 未配置环境变量账号,执行 `akm-node login`
- **THEN** 交互输入 Hub 地址与账号密码换取凭证,成功后自动进入运行循环(与既有规格一致)
