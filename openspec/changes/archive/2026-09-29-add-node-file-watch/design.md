# Design: add-node-file-watch

## Context

现状触发时机与协议见 `multi-node-sync` 能力;痛点分析、批次定位与完整实现设计见 [docs/node-realtime-sync-design.md](../../../docs/node-realtime-sync-design.md)。本文只记录需要固化的架构决策与取舍。

## Goals / Non-Goals

**Goals:**

- 本地文档变更到 Hub 可见的延迟 < 10 秒(典型场景)
- 监听丢事件时,定时对账保证最终一致
- 复用既有 hash-first 协议与快照语义,**服务端零改动**

**Non-Goals:**

- 非 Markdown 格式接入(PDF / Word / HTML 转换)——独立批次
- 排除规则的用户可配置化(`.akmignore`)——仅内置规则
- Hub 侧反向下发(节点拉取其他机器的文档)——未排期
- 节点进程的服务化注册——托管模板属 `deploy/`,不在本变更

## Decisions

1. **选 `watchfiles` 而非 `watchdog`**:原生 async(`awatch()`),与现有 asyncio 编排(心跳、消息处理均为 task)风格一致;自带 `debounce` 参数;uvicorn 已依赖,不引入新生态。watchdog 为线程模型,需跨线程桥接(弃)。
2. **监听与对账并存,而非二选一**:监听负责实时(低延迟),对账负责最终一致(兜底)。仅监听会在跨平台 / 网络文件系统场景静默漏事件;仅轮询延迟不可控。
3. **局部 diff 不得产生 `deletions`**:监听触发时只对变更文件构造差异;快照中存在但本轮未扫描到的路径**不代表被删除**,只有捕获到 `deleted` 事件的路径才进 `deletions`。这是局部同步与全量同步的核心区别,实现须显式区分——否则会误删其他文件。**本变更最关键的一条约束,单测必须覆盖。**
4. **防抖交给 `watchfiles` 的 `debounce` 参数**(默认 3000ms),不自行实现事件聚合;写入稳定性另做 `stat` 双检(间隔 300ms,`st_size` 与 `st_mtime_ns` 均未变),不稳定则跳过该文件,**由对账兜底**、不阻塞本轮其他文件。
5. **过滤语义与 `scanner.py` 对齐并下沉到 `akm_shared`**:两处判定不一致会导致"监听到了但扫描不到"(或反之)的诡异行为。内置排除目录须含 `node_modules`——它不以 `.` 开头,`scanner.py` 现有的隐藏项规则覆盖不到。
6. **并发保护用 `asyncio.Lock` 串行化上传**,后到请求合并等待。目的是省流量,不是保正确性——"快照仅在 200 后更新"的既有语义已保证幂等。
7. **监听 / 对账循环不参与主链路竞争退出**:`runner.py` 现用 `asyncio.wait(FIRST_COMPLETED)` 决定重连时机,新增循环若参与其中会让心跳正常结束也触发重连。两循环内部捕获全部异常并退避重试,不向上抛。
8. **容器场景默认关闭监听**:Windows / macOS 宿主的 Docker bind mount 不传播 inotify 事件,监听会静默失效(比报错更危险)。`deploy/docker-compose.node.yml` 置 `AKM_WATCH_ENABLED=false`,依赖对账,并在启动日志显式提示"监听已关闭"。

## Risks / Trade-offs

- [监听任务异常拖垮主链路] → 见 Decisions 7;两循环内部兜住全部异常
- [局部 diff 误删其他文件] → 见 Decisions 3;单测覆盖(最关键用例)
- [全量对账成本] → 需读取并哈希全部文件。中小知识库为秒级;超大知识库可调大间隔或置 `0` 关闭。本期接受,以实际规模调优
- [文件写入未完成即读取] → 防抖 + `stat` 双检;仍不稳定则跳过,由对账兜底
- [跨平台事件差异 / 网络文件系统] → 对账兜底;在 `docs/deployment.md` 标注限制
- [监听范围与扫描范围漂移] → 见 Decisions 5;判定下沉共用

## Migration Plan

1. 节点侧升级即可,服务端无需改动,无先后顺序约束
2. 回滚:降级节点版本后恢复"仅启动 / 请求触发",快照格式不变,无数据迁移
3. 已有节点升级后首次启动:监听立即生效;首轮仍走全量 diff(快照已有内容则近乎零流量)

## Open Questions

- 对账间隔默认 300 秒是否合适——以实际知识库规模在实施后调优,必要时按规模自适应
