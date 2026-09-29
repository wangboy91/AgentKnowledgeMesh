# document-management 能力增量(写入作用域与唯一性)

## MODIFIED Requirements

### Requirement: Document Creation
系统 SHALL 提供 `POST /api/documents` 端点，接收 `path`、`title`、`content` 创建新文档。**路径唯一性 SHALL 以 `(node_id, path)` 判定:同一归属下路径重复返回 409,不同归属的同名路径可共存。文档归属 SHALL 由调用者凭证决定:节点凭证创建时 `node_id` 强制为该节点(不接受请求体指定),用户与 API Token 凭证创建时归属 `local`。** 新文档的初始 `rag_status` SHALL 由「向量化总开关 + `rag_sync_mode`」决定:仅当总开关开启且模式为 `auto` 时置 `indexed` 并尽力同步向量索引,其余情况置 `not_indexed` 且不产生向量操作。

#### Scenario: 创建成功
- **WHEN** 客户端提交该归属下不冲突路径的文档
- **THEN** 系统计算 SHA256 哈希与字节大小并入库，返回完整文档记录

#### Scenario: 自动模式且向量化开启时同步向量
- **WHEN** 向量化总开关开启、模式为 `auto`,文档创建成功
- **THEN** 文档 `rag_status` 为 `indexed`,系统尽力同步其向量索引;失败不影响创建结果

#### Scenario: 其余情况不入向量
- **WHEN** 向量化总开关关闭,或模式为 `manual`
- **THEN** 文档 `rag_status` 为 `not_indexed`,无任何向量操作

#### Scenario: 路径冲突
- **WHEN** 提交路径在同一归属(`node_id` 相同)下已存在
- **THEN** 系统返回 409，`detail` 为 "Document already exists at this path"

#### Scenario: 不同归属的同名路径可共存
- **WHEN** 提交的路径已存在于其他 `node_id` 名下,而本归属下不存在
- **THEN** 创建成功,不返回冲突

#### Scenario: 节点凭证创建的归属
- **WHEN** 以节点凭证调用创建端点,且请求体不含或含任意 `node_id`
- **THEN** 新文档的 `node_id` 为该节点(请求体的 `node_id` 不被采纳)

#### Scenario: 标题缺省时自动提取
- **WHEN** 未提供标题或标题为空
- **THEN** 系统依次尝试从内容前 5 行中提取 `# ` 标题，否则使用路径文件名（去扩展名）

### Requirement: Document Update
系统 SHALL 提供 `PUT /api/documents/{doc_id}` 端点，接收 `content` 更新文档正文。**以节点凭证调用时 SHALL 仅允许更新 `node_id` 等于该节点的文档,跨作用域更新返回 403。** 更新后的 `rag_status` SHALL 按同一策略重设:仅「总开关开启 + auto」置 `indexed` 并尽力更新向量,其余置 `not_indexed`;用户显式 `excluded` 的文档 SHALL 保持 `excluded`。

#### Scenario: 更新正文并重算元信息
- **WHEN** 客户端提交新内容
- **THEN** 系统更新内容、重算 SHA256 哈希与字节大小，并在内容前 5 行存在 `# ` 标题时更新标题

#### Scenario: 更新后同步向量索引
- **WHEN** 向量化总开关开启、模式为 `auto`,文档更新成功
- **THEN** 文档 `rag_status` 为 `indexed`,系统尽力更新该文档的向量索引；向量更新失败不影响文档更新结果

#### Scenario: 其余情况不入向量
- **WHEN** 向量化总开关关闭,或模式为 `manual`,文档更新成功
- **THEN** 文档 `rag_status` 为 `not_indexed`,无任何向量操作

#### Scenario: 显式排除的文档不被拉回
- **WHEN** 更新一篇 `rag_status` 为 `excluded` 的文档
- **THEN** 更新后该文档 `rag_status` 仍为 `excluded`

#### Scenario: 更新不存在的文档
- **WHEN** 客户端请求更新不存在的文档 ID
- **THEN** 系统返回 404

#### Scenario: 节点凭证跨作用域更新被拒
- **WHEN** 以节点凭证更新归属其他节点或 `local` 的文档
- **THEN** 系统返回 403,文档不被修改
