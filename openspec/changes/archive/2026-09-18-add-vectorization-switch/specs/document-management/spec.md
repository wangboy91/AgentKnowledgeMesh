# document-management 能力增量

## MODIFIED Requirements

### Requirement: Document Creation
系统 SHALL 提供 `POST /api/documents` 端点，接收 `path`、`title`、`content` 创建新文档。**新文档的初始 `rag_status` SHALL 由「向量化总开关 + `rag_sync_mode`」决定:仅当总开关开启且模式为 `auto` 时置 `indexed` 并尽力同步向量索引,其余情况置 `not_indexed` 且不产生向量操作。**

#### Scenario: 创建成功
- **WHEN** 客户端提交不冲突路径的文档
- **THEN** 系统计算 SHA256 哈希与字节大小并入库，返回完整文档记录

#### Scenario: 自动模式且向量化开启时同步向量
- **WHEN** 向量化总开关开启、模式为 `auto`,文档创建成功
- **THEN** 文档 `rag_status` 为 `indexed`,系统尽力同步其向量索引;失败不影响创建结果

#### Scenario: 其余情况不入向量
- **WHEN** 向量化总开关关闭,或模式为 `manual`
- **THEN** 文档 `rag_status` 为 `not_indexed`,无任何向量操作

#### Scenario: 路径冲突
- **WHEN** 提交路径与现有文档重复
- **THEN** 系统返回 409，`detail` 为 "Document already exists at this path"

#### Scenario: 标题缺省时自动提取
- **WHEN** 未提供标题或标题为空
- **THEN** 系统依次尝试从内容前 5 行中提取 `# ` 标题，否则使用路径文件名（去扩展名）

### Requirement: Document Update
系统 SHALL 提供 `PUT /api/documents/{doc_id}` 端点，接收 `content` 更新文档正文。**更新后的 `rag_status` SHALL 按同一策略重设:仅「总开关开启 + auto」置 `indexed` 并尽力更新向量,其余置 `not_indexed`。**

#### Scenario: 更新正文并重算元信息
- **WHEN** 客户端提交新内容
- **THEN** 系统更新内容、重算 SHA256 哈希与字节大小，并在内容前 5 行存在 `# ` 标题时更新标题

#### Scenario: 更新后同步向量索引
- **WHEN** 向量化总开关开启、模式为 `auto`,文档更新成功
- **THEN** 文档 `rag_status` 为 `indexed`,系统尽力更新该文档的向量索引；向量更新失败不影响文档更新结果

#### Scenario: 其余情况不入向量
- **WHEN** 向量化总开关关闭,或模式为 `manual`,文档更新成功
- **THEN** 文档 `rag_status` 为 `not_indexed`,无任何向量操作

#### Scenario: 更新不存在的文档
- **WHEN** 客户端请求更新不存在的文档 ID
- **THEN** 系统返回 404

### Requirement: Document RAG Status Visibility
文档列表与详情 SHALL 携带 `rag_status` 字段(`not_indexed` / `pending` / `indexed` / `excluded`);文档列表 SHALL 支持按 `rag_status` 过滤(`GET /api/documents?rag_status=excluded` 等)。

#### Scenario: 列表携带状态
- **WHEN** 客户端调用 `GET /api/documents`
- **THEN** 每项包含 `rag_status` 字段

#### Scenario: 按状态过滤
- **WHEN** 客户端调用 `GET /api/documents?rag_status=excluded`
- **THEN** 仅返回 `rag_status` 为 `excluded` 的文档

#### Scenario: 未向量化与已排除可区分
- **WHEN** 向量化关闭或模式为 `manual` 时新入库的文档,与用户显式"移出 RAG"的文档并存
- **THEN** 前者 `rag_status` 为 `not_indexed`、后者为 `excluded`,过滤与展示均可区分
