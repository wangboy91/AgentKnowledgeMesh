# account-auth 能力增量

## ADDED Requirements

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
