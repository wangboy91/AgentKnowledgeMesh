# mcp-integration 能力增量(智能体写回)

## MODIFIED Requirements

### Requirement: Node Local MCP Proxy Behavior
节点本地 MCP 代理 SHALL 将工具调用转调 Hub HTTP API 并携带节点凭证:`search_documents` → `GET /api/search`(支持可选语义模式)、`get_document` → `GET /api/documents/{id}`、`list_documents` → `GET /api/documents`、`create_document` → `POST /api/documents`、`update_document` → `PUT /api/documents/{id}`。**写工具转调 SHALL NOT 传递或允许覆盖 `node_id`——归属与作用域一律由 Hub 依据节点凭证判定。** Hub 不可达或返回鉴权失败时,SHALL 返回包含原因的明确错误信息,而非崩溃或挂起。

#### Scenario: 经代理搜索
- **WHEN** 智能体对节点代理调用 `search_documents`
- **THEN** 代理携带节点凭证请求 Hub 搜索端点,返回与 Hub MCP 一致格式的结果

#### Scenario: 经代理写入
- **WHEN** 智能体对节点代理调用 `create_document` 或 `update_document`
- **THEN** 代理携带节点凭证分别请求 `POST /api/documents` 与 `PUT /api/documents/{id}`,返回与 Hub MCP 一致格式的结果

#### Scenario: 代理写入不携带 node_id
- **WHEN** 代理转发写工具的调用
- **THEN** 请求体不含 `node_id` 字段,写入归属由 Hub 依节点凭证强制为本节点

#### Scenario: 写入被 Hub 拒绝
- **WHEN** Hub 对代理的写请求返回 409(路径冲突)或 403(跨节点越权)
- **THEN** 代理返回对应的可操作错误文本(路径已存在 / 无权写入该文档),进程保持可用

#### Scenario: Hub 不可达
- **WHEN** 节点代理无法连接 Hub
- **THEN** 工具返回 "无法连接 Hub(<地址>):请检查 Hub 状态" 类错误信息,进程保持可用

#### Scenario: 凭证失效
- **WHEN** Hub 对节点凭证返回 401
- **THEN** 工具返回 "节点凭证已失效,请重新执行 akm-node login" 类错误信息

#### Scenario: 检索质量由 Hub 保证
- **WHEN** 任意接入形态执行语义相关查询
- **THEN** 语义检索能力仅由 Hub 提供,节点代理不实现本地向量检索

## ADDED Requirements

### Requirement: Create Document Tool
MCP Server SHALL 提供 `create_document` 工具,参数为必填 `path`、`content` 与可选 `title`,在知识库中新建一篇 Markdown 文档。**文档归属 SHALL 由调用者凭证决定:节点凭证写入的文档归属该节点(`node_id` 强制为该节点,不接受调用方指定),用户与 API Token 凭证写入的文档归属 `local`。** 路径唯一性 SHALL 以 `(node_id, path)` 判定;同节点下路径已存在时 SHALL 返回冲突错误并提示改用 `update_document`。成功时 SHALL 返回含 `id`、`title`、`path`、`node_id`、大小与更新时间的文本结果。

#### Scenario: 创建成功
- **WHEN** Agent 调用 `create_document` 提交该归属下不冲突的 `path` 与 `content`
- **THEN** 系统计算 SHA256 与字节大小并入库,返回含新文档 `id` 的结果文本

#### Scenario: 节点凭证创建的归属
- **WHEN** 节点代理以节点凭证调用 `create_document`
- **THEN** 新文档的 `node_id` 为该节点,出现在该节点的文档分支下

#### Scenario: 路径冲突
- **WHEN** 提交的 `path` 在该归属下已存在
- **THEN** 工具返回冲突错误文本,提示改用 `update_document`,不产生写入

#### Scenario: 不同节点的同名路径可共存
- **WHEN** 另一节点名下已存在相同 `path`,本节点创建同名路径
- **THEN** 创建成功,不返回冲突

#### Scenario: 标题缺省时自动提取
- **WHEN** 未提供 `title` 或为空
- **THEN** 系统依次尝试从内容前 5 行提取 `# ` 标题,否则使用路径文件名(去扩展名)

#### Scenario: 写入后按策略处理向量
- **WHEN** 创建成功且向量化总开关开启、模式为 `auto`
- **THEN** 文档 `rag_status` 为 `indexed` 并尽力同步向量索引;其余组合置 `not_indexed` 且无向量操作

#### Scenario: 缺少必填参数
- **WHEN** 调用未提供 `path` 或 `content`
- **THEN** 工具返回 "缺少参数: <名称>" 类错误文本,不产生写入

### Requirement: Update Document Tool
MCP Server SHALL 提供 `update_document` 工具,参数为必填 `document_id` 与 `content`,覆盖更新已有文档正文。**以节点凭证调用时,SHALL 仅允许更新 `node_id` 等于该节点的文档,跨节点更新 SHALL 返回越权错误。** 文档不存在时 SHALL 返回"文档 ID <id> 不存在。"类提示。更新 SHALL 重算 SHA256 与字节大小,并在内容前 5 行存在 `# ` 标题时更新标题;用户显式 `excluded` 的文档 SHALL 保持 `excluded`。

#### Scenario: 更新成功
- **WHEN** Agent 调用 `update_document` 传入存在的文档 ID 与新正文
- **THEN** 系统更新内容、重算哈希与大小、按需更新标题,返回含更新时间的结果文本

#### Scenario: 跨节点更新被拒
- **WHEN** 以某节点凭证更新归属其他节点(或 `local`)的文档
- **THEN** 工具返回越权错误文本,不产生写入

#### Scenario: 文档不存在
- **WHEN** 传入不存在的文档 ID
- **THEN** 工具返回 "文档 ID <id> 不存在。"

#### Scenario: 更新后按策略处理向量
- **WHEN** 更新成功且向量化总开关开启、模式为 `auto`,文档未被显式排除
- **THEN** 文档 `rag_status` 为 `indexed` 并尽力更新向量索引;其余组合置 `not_indexed`

#### Scenario: 显式排除的文档不被拉回
- **WHEN** 更新一篇 `rag_status` 为 `excluded` 的文档
- **THEN** 更新后 `rag_status` 仍为 `excluded`

#### Scenario: 缺少必填参数
- **WHEN** 调用未提供 `document_id` 或 `content`
- **THEN** 工具返回 "缺少参数: <名称>" 类错误文本,不产生写入
