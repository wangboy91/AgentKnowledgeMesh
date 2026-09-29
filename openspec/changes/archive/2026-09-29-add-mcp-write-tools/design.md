# Design: add-mcp-write-tools

## Context

现状鉴权、写端点与 MCP 工具集见 `mcp-integration` / `account-auth` / `document-management` 三个能力;痛点分析、批次定位与完整实现设计见 [docs/agent-write-back-design.md](../../../docs/agent-write-back-design.md)。本文只记录需要固化的架构决策与取舍。

## Goals / Non-Goals

**Goals:**

- 智能体可经三种 MCP 形态**写回**知识(新建 / 覆盖更新),写回内容立即进入既有检索与分发通道
- 节点凭证获得**受限写能力**:只能写本节点名下的文档,爆炸半径可控
- 写入口径(REST / Hub MCP)单源,杜绝两处 hash / 标题 / rag_status 漂移
- **零 LLM 依赖**:不引入任何生成式模型

**Non-Goals:**

- `delete_document`——删除需审计与回收站,归批次 5 治理
- wiki 页数据模型(`doc_type` / `derived_from` / stale)——批次 2
- 服务端 distiller / 生成式 LLM 调用——批次 4
- Hub 反向下发(节点拉取其他机器文档)——未排期
- 并发写冲突检测(乐观锁)——留待有真实诉求时评估
- 按路径 upsert 单工具语义——坚持 create / update 分离,语义显式

## Decisions

1. **REST 是契约,MCP 工具是其薄封装**:节点代理形态必须经 HTTP,故 REST 写端点先行;Hub 两形态虽可直连 DB,业务口径必须与 REST 逐字一致(由 Decisions 3 的单源保证)。
2. **鉴权第三态而非放宽 `allow_node`**:`require_auth(min_role, allow_node, node_write)`。`allow_node=True` 语义是"放行节点凭证(只读端点)",若直接改它含义会让所有只读端点的语义变模糊;新增 `node_write=True` 表达"节点可写,但作用域由端点在业务层校验"。**作用域校验必须在端点做**——`require_auth` 拿不到目标文档,无从判断归属。
3. **写入口径抽 `services/document_writer.py` 单源**:Hub MCP 直连 DB,若不抽取就会复制一份 create/update 逻辑。两处漂移会让"经 MCP 写的"与"经 REST 写的"文档在 hash / 标题 / `rag_status` 上不一致——隐性 bug 温床。该模块只做业务口径,不做权限与作用域(那是端点职责)。
4. **唯一性统一为 `(node_id, path)`**:DB 约束与节点同步协议本就是该口径,唯 REST create 例外(全局 path)。多机下 `notes/todo.md` 同名是常态,原口径会让写回在最常见场景 409。这是**放宽**,不破坏既有成功路径。
5. **`update` 用 `document_id` 而非 `path`**:与既有 `get_document(document_id)` 词汇一致,与 REST `PUT /api/documents/{doc_id}` 一一对应,节点代理零歧义转发。跨会话取 id 由 `search_documents` 承担,不算额外负担。
6. **节点写入归属强制 `principal.node_id`**:create 不接受调用方指定 `node_id`,杜绝冒充其他节点;update 校验 `doc.node_id == principal.node_id`。写回的文档与节点扫描文档同域——若本地磁盘也有同路径文件,下次扫描按 `(node_id, path)` 命中同一条记录并按 hash 收敛,不产生重复。
7. **不新增配置开关**:写能力由权限模型天然约束(admin / 节点凭证)。不想要写回,不给节点配 MCP 代理即可。向量化沿用既有总开关与 `rag_sync_mode`,写回文档的 `rag_status` 走同一策略(`excluded` 粘性不变)。
8. **错误分两类**:业务性错误(409 路径冲突 / 403 越权 / 404 不存在)返回普通文本、`isError` 不置位;基础设施错误(连接 / 超时 / 401)返回 `isError=True` + 可操作文案。与既有三工具一致。

## Risks / Trade-offs

- [唯一性口径变更影响既有调用方] → 变更方向是放宽(原 409 → 可能 200),不破坏成功路径;在 `api-reference.md` 与 delta 中显式标注
- [节点凭证写权限过宽] → 作用域严格限 `principal.node_id`;不能删除、不能改他人与 `local`;单测覆盖跨节点 403
- [REST 与 MCP 口径漂移] → 见 Decisions 3;单测断言两侧写入结果字段一致
- [MCP 工具定义双侧人工同步] → 既有三工具已有该约束(`mcp_proxy.py` 注释标注"改动需两侧同步");本变更沿用同一机制,输出格式化下沉 `akm_shared` 降低漂移面
- [写回不落本地磁盘] → 文档仅在 Hub DB;智能体若需本地副本须自行写文件,随后由监听 / 对账收敛。在 `docs/agent-write-back-design.md` 标注限制
- [并发覆盖写] → 后写覆盖先写(与现有 REST 行为一致);无冲突检测,留待治理批次

## Migration Plan

1. 服务端与节点可独立升级:服务端先行(提供写端点与权限),节点代理随后(转发写工具)。**顺序有约束**:先升服务端,再升节点;反之节点代理会 404
2. 回滚:降级服务端后写端点恢复 admin-only,节点代理的写工具调用返回 403/404——读工具不受影响,无数据迁移
3. 无 schema 变更:复用 `Document` 表与 `(node_id, path)` 既有唯一约束

## Open Questions

- 是否需要在文档上记录"写入来源"(智能体 / 人工 / 扫描)以便审计——批次 2 的 `doc_type` 可承载,届时一并设计
- 是否要限制单次写入体积上限(防智能体灌入超长内容)——当前沿用 REST 既有行为(无显式上限),实际出现滥用再评估
