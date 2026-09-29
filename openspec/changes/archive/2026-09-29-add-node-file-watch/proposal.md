# Proposal: add-node-file-watch

## Why

节点当前只在**初始连接成功后**与**收到 Hub `sync_request` 时**推送文档变更(见 `multi-node-sync` 能力的 `Node Document Upload`)。本地文档的增删改**不产生任何事件**:在一台电脑上改完文档,Hub 与其余节点无从知晓,必须重启节点进程,或由管理员在 Web 节点页手动触发同步。

多机知识共享因此实际处于"手动挡":文档改动到其他电脑可见之间的延迟不可控,各机智能体检索到的可能是过期内容。这是当前多机场景最主要的体验断点——其余能力(检索、MCP 接入、文档树)都建立在"Hub 拥有最新语料"这个前提之上。

## What Changes

- 节点新增**文件变更监听**:监听 `AKM_KNOWLEDGE_ROOTS` 下的 `.md`,变更事件经过滤与防抖后自动触发增量同步(复用现有 hash-first 差异分类与上传协议)
- 节点新增**定时全量对账**(默认 300 秒):全量扫描 + hash 比对,兜住监听丢事件的场景,保证最终一致
- 同步调用**并发保护**:监听 / 对账 / Hub 请求同时到达时串行化,避免重复上传
- 过滤判定下沉到 `akm_shared`,供扫描器与监听共用,避免两处语义漂移
- 新增节点配置项:`AKM_WATCH_ENABLED`、`AKM_WATCH_DEBOUNCE_SECONDS`、`AKM_WATCH_RECONCILE_SECONDS`、`AKM_WATCH_EXCLUDE`;新增依赖 `watchfiles`
- **服务端零改动**:上传协议、鉴权、快照格式全部沿用

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `multi-node-sync`: `Node Document Upload` 的触发时机从"初始连接成功后与收到 `sync_request` 时"扩展为"另含本地文件变更事件与定时对账";新增 `Node File Change Watch` 要求,规定监听范围、过滤规则、防抖与对账语义,以及局部同步不得产生隐式删除

## Impact

- **node**:新增监听与对账循环(`runner.py`)、局部增量路径与并发保护(`sync.py`)、配置项(`config.py`)、依赖(`pyproject.toml`)
- **shared**:过滤判定下沉(`akm_shared`),`scanner.py` 改用共用判定(行为不变)
- **server**:无改动
- **deploy**:安装脚本附托管模板(systemd / launchd / 计划任务 / pm2)、节点 compose 关闭监听——属编排改动,按 `workflow.md` §2 **直接改**,不在本变更内
- **兼容**:新旧节点可并存,老节点行为不变;快照格式不变,无需迁移
- **验证**:改动一个 `.md` 后,Hub 端该文档 `updated_at` 更新延迟 < 10 秒
