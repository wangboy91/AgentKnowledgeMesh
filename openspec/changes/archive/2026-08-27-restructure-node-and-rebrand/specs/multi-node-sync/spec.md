## MODIFIED Requirements

### Requirement: Node Identity
Node 客户端 SHALL 在未显式配置时自动生成本机身份：`node_id` 由主机名确定性生成（UUID5），`name` 默认为主机名，`platform` 为小写操作系统名（darwin/windows/linux）。

#### Scenario: 同机重启身份不变
- **WHEN** 同一台机器未配置 `AKM_NODE_ID` 并重启 Node
- **THEN** 生成的 `node_id` 与之前相同，Hub 识别为同一节点

#### Scenario: 显式配置优先
- **WHEN** 配置了 `AKM_NODE_ID` 或 `AKM_NODE_NAME`
- **THEN** Node 使用配置值而非自动生成值

### Requirement: Heartbeat Keep-Alive
Node SHALL 周期性向 Hub 发送 `heartbeat` 消息（默认间隔 30 秒，可通过 `AKM_HEARTBEAT_INTERVAL` 配置）；Hub SHALL 以心跳刷新节点在线状态。

#### Scenario: 心跳刷新状态
- **WHEN** Hub 收到节点的 `heartbeat` 消息
- **THEN** Hub 更新该节点 `last_heartbeat` 为当前时间、状态置为 `online`，并返回 `{"type": "heartbeat_ack"}`
