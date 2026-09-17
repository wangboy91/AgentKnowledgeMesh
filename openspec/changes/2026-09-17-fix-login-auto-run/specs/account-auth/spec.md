# account-auth 能力增量

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: 节点 CLI 帮助
节点 CLI SHALL 提供 `--help` / `-h` 输出:列出全部命令与用法(`login`、默认运行、`--mcp`、`--version`),并说明断开方式(Ctrl+C)与断线自动重连(默认 5 秒间隔)行为;帮助输出后 SHALL 以退出码 0 结束,不启动客户端。

#### Scenario: 查看帮助
- **WHEN** 执行 `akm-node --help` 或 `akm-node -h`
- **THEN** 输出命令列表、断开方式与断线重连说明,进程以退出码 0 结束

#### Scenario: 帮助优先于其他行为
- **WHEN** 携带 `--help` 的命令行同时包含其他参数
- **THEN** 仅输出帮助并退出,不触发登录或客户端启动
