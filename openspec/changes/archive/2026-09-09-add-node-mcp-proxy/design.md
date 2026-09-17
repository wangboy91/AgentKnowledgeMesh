# Design: add-node-mcp-proxy

## Context

现状:MCP Server 仅存在于 Hub(`app/services/mcp_server.py`,stdio + SSE 两种形态,工具直查 Hub 库);节点为纯同步客户端。方案详见 [docs/technical-design.md](../../../docs/technical-design.md) §9。

## Goals / Non-Goals

**Goals:**
- 智能体接入零 Hub 配置:一条 `akm-node --mcp` 命令,凭证留在节点本机
- 三形态工具集与返回格式完全一致(智能体无感切换)
- Hub 故障时错误信息可操作(指向 login/Hub 状态)

**Non-Goals:**
- 节点本地向量检索、离线降级(V1.0 备选)
- 节点间 MCP 联邦、多 Hub 路由
- MCP resources/prompts 能力(仅 tools,与 Hub 现状一致)

## Decisions

1. **stdio 而非本地端口服务**:智能体按 MCP 惯例拉起子进程,免端口管理、免守护进程、生命周期随会话;备选(节点常驻 localhost SSE)需要端口分配与进程管理,复杂度高,弃。
2. **转调 REST 而非 MCP 协议转发**:节点直接调 Hub HTTP API(复用 httpx 与同步通道的连接管理),不嵌 MCP 客户端 —— 少一层协议栈,错误处理直白。
3. **复用 Hub MCP 工具的格式化逻辑**:把三个工具的"结果 → 文本"格式化函数抽到 `akm_shared`(或复制对齐,实现时按耦合度定),保证三形态输出一致;工具的 Hub 端实现不动。
4. **凭证读取**:与同步共用 `AKM_NODE_ID` / `AKM_NODE_TOKEN`(.env);`--mcp` 模式不启动同步循环(单职责短生命周期进程)。
5. **超时与降级**:Hub 调用统一 10s 超时;连接失败/401/超时分别映射为可操作错误文本,进程不退出(MCP 会话保持)。

## Risks / Trade-offs

- [与 Hub MCP 工具行为漂移] → 格式化逻辑单源(共享或对齐测试),tasks 含三形态输出一致性验证
- [node token 只读授权未就位] → 硬依赖 add-account-auth 的 node token 白名单;本变更验证步骤显式覆盖 401 路径
- [stdio 子进程环境差异(Windows 编码)] → 入口已有 UTF-8 reconfigure;MCP stdio 协议本身 UTF-8

## Migration Plan

1. 依赖 add-account-auth 合入(node token 只读授权)
2. 节点升级后智能体改配 `akm-node --mcp`(旧 Hub SSE 配置继续可用,无强制迁移)
3. 回滚:智能体配置切回 SSE 即可,节点模式残留无害

## Open Questions

无。
