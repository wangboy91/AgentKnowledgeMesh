# Proposal: add-mcp-write-tools

## Why

知识库对智能体是**只读**的。三种 MCP 接入形态只暴露 `search_documents` / `get_document` / `list_documents` 三个读工具;REST 写端点(`POST /api/documents`、`PUT /api/documents/{doc_id}`)一律要求 admin JWT,节点凭证被硬编码拒绝(`403 Node credentials are read-only`)。

后果:知识只能经**人工编辑**与**文件扫描**两个通道流入。智能体读了语料、得出结论、写出总结,这段总结无处安放——留在对话里,下轮从零开始。

批次 1(`add-node-file-watch`)已让本地文档变更**实时到达** Hub;但智能体**无法产生**变更。写回是"读 → 加工 → 写回 → 别处读到"闭环的最后一环:补上它,多机知识共享痛点才算真正收口(批次 1 → 批次 3 最短路径)。

## What Changes

- MCP 新增两个**写工具**,三形态(Hub SSE / Hub stdio / 节点本地代理)同名同参同输出:
  - `create_document(path, content, title?)`
  - `update_document(document_id, content)`
- **鉴权模型扩展**:`require_auth` 引入第三态——节点凭证对文档写端点放行,但**作用域限 `principal.node_id`**(创建强制归属本节点;更新仅限本节点名下文档,跨节点 403)。其余写端点仍仅限 admin
- **文档唯一性口径统一为 `(node_id, path)`**:REST create 从"全局 path 唯一"改为与 DB 约束、与节点同步协议一致。这是契约变更——`notes/todo.md` 这类通用路径在多机下共存是常态,原口径会让写回在最常见场景直接 409
- **写入口径单源**:抽取 `app/services/document_writer.py`,统一 create/update 的标题提取、SHA256、字节大小、`rag_status` 策略与提交刷新,供 REST 端点与 Hub MCP 处理器共用,避免两处漂移
- **节点代理新增写通道**:`mcp_proxy.py` 增加 `_hub_write` / `_safe_hub_write`,转调 Hub REST(不传递、不允许覆盖 `node_id`)
- **输出格式单源**:`akm_shared.mcp_formatting` 新增 `format_document_created` / `format_document_updated`
- **零 LLM**:写什么由调用方决定,AKM 只提供存储与通道

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `mcp-integration`:新增 `Create Document Tool` 与 `Update Document Tool` 两个要求;`Node Local MCP Proxy Behavior` 扩展为同时转发写工具(带节点凭证,作用域由 Hub 强制)
- `account-auth`:`端点鉴权矩阵` 从"写操作仅限 admin、节点凭证只读"调整为"文档写端点对节点凭证放行且作用域限本节点",其余写端点维持 admin-only
- `document-management`:`Document Creation` 的唯一性口径由全局 `path` 改为 `(node_id, path)`,并明确节点凭证创建的归属;`Document Update` 增加节点凭证作用域校验

## Impact

- **server**:`services/auth.py`(鉴权第三态)、新增 `services/document_writer.py`(写入口径单源)、`api/documents.py`(两写端点鉴权与唯一性)、`services/mcp_server.py`(两个写工具)
- **node**:`app/mcp_proxy.py`(写通道与两个工具)
- **shared**:`akm_shared/mcp_formatting.py`(创建 / 更新结果格式化)
- **docs**:新增 `docs/agent-write-back-design.md`;`api-reference.md` 标注端点鉴权与唯一性变化;`README.md` 功能列表
- **兼容**:MCP 为纯增量(老客户端不感知);REST 端点路径与请求体不变,仅鉴权放宽与唯一性放宽——不会让原本成功的请求失败
- **安全边界**:节点凭证的爆炸半径限定为"写自己名下文档";不能删除、不能改其他节点、不能改 `local`
- **验证**:经节点代理 `create_document` 写入 → 另一台机器的智能体经其代理 `search_documents` 命中该文档(闭环)
