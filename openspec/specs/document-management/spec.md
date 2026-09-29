# document-management 能力规格

## Purpose

提供文档列表、文件树、详情、创建与编辑的 REST API，以及系统统计与健康检查，支撑 Web 前端浏览与生产环境的知识库维护。

## Requirements

### Requirement: Document Listing
系统 SHALL 提供 `GET /api/documents` 端点，返回全部文档的元信息列表（不含正文），按更新时间倒序排列。

#### Scenario: 列出文档元信息
- **WHEN** 客户端调用 `GET /api/documents`
- **THEN** 系统按 `updated_at` 倒序返回文档列表，每项包含 id、node_id、path、title、hash、size、tags、created_at、updated_at，但不含 content

### Requirement: Document Tree
系统 SHALL 提供 `GET /api/documents/tree` 端点,将文档路径组织为文件树;SHALL 支持可选 `node_id`(按节点过滤)与可选 `dir`(目录切片)查询参数;文件节点 SHALL 携带 `id`。

**缺省(不传 `dir`)时返回完整嵌套树(向后兼容);传 `dir`(含空串=根)时 SHALL 仅返回该目录的一层直接子项:文件节点为 `{_title, _path, _rag_status, id}`,子目录为 `{}` 占位。**

#### Scenario: 按路径层级构建树
- **WHEN** 索引中存在文档 `projects/ai-crm.md`(标题 "AI CRM System Design")
- **THEN** 返回结构为 `{"projects": {"ai-crm.md": {"_title": "AI CRM System Design", "_path": "projects/ai-crm.md", "_rag_status": "<状态>", "id": <文档 ID>}}}`,目录层级逐层嵌套

#### Scenario: 按节点过滤
- **WHEN** 客户端调用 `GET /api/documents/tree?node_id=<某节点>`
- **THEN** 树仅包含该节点名下的文档,其他节点(含 `local`)文档不出现

#### Scenario: 目录切片一层性
- **WHEN** 索引存在 `docs/a.md` 与 `docs/sub/b.md`,客户端调用 `GET /api/documents/tree?dir=docs`
- **THEN** 返回 `{"a.md": {...含 id...}, "sub": {}}`,不包含 `b.md`(仅一层)

#### Scenario: 根切片
- **WHEN** 客户端调用 `GET /api/documents/tree?dir=`(空串)
- **THEN** 返回顶层一层子项(顶层目录为 `{}` 占位,顶层文件带完整元信息)

#### Scenario: 不存在的目录
- **WHEN** 客户端调用 `GET /api/documents/tree?dir=ghost`
- **THEN** 返回 `{}`

#### Scenario: 特殊字符目录名
- **WHEN** 目录名含 `%` 或 `_` 等 LIKE 通配字符
- **THEN** 切片仍精确匹配该目录,不误匹配其他目录

#### Scenario: 缺省参数兼容
- **WHEN** 客户端调用 `GET /api/documents/tree`(不带 `node_id` 与 `dir`)
- **THEN** 返回全部节点文档构成的完整嵌套树,与既有行为一致(叶子多 `id` 字段)

### Requirement: Document Detail
系统 SHALL 提供 `GET /api/documents/{doc_id}` 端点，返回单个文档的完整信息（含正文）。

#### Scenario: 获取存在的文档
- **WHEN** 客户端请求存在的文档 ID
- **THEN** 系统返回该文档全部字段及 `content` 正文

#### Scenario: 文档不存在
- **WHEN** 客户端请求不存在的文档 ID
- **THEN** 系统返回 404，`detail` 为 "Document not found"

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

### Requirement: System Statistics
系统 SHALL 提供 `GET /api/stats` 端点，返回知识库总体统计。

#### Scenario: 返回统计信息
- **WHEN** 客户端调用 `GET /api/stats`
- **THEN** 系统返回 `total_documents`（文档总数）、`total_size_bytes`（总字节数）、`total_nodes`（注册节点总数）、`online_nodes`（当前在线节点数）

### Requirement: Health Check
系统 SHALL 提供 `GET /api/health` 端点用于健康检查。

#### Scenario: 返回运行状态
- **WHEN** 客户端调用 `GET /api/health`
- **THEN** 系统返回 `{"name": <应用名>, "version": <版本号>, "status": "running"}`

### Requirement: Production SPA Serving
系统 SHALL 在生产模式下（存在前端构建产物时）托管静态资源，并对非 API 路径提供 SPA 路由回退；返回的 `index.html` SHALL 携带当前部署前缀作为文档基址与运行时基址（见 `subpath-deployment` 能力），使同一份构建产物可在任意深度子路径下运行。

#### Scenario: 前端路由回退
- **WHEN** 请求的非 API 路径在静态目录中没有对应文件
- **THEN** 系统返回 `index.html`，由前端路由接管

#### Scenario: 回退页面携带部署基址
- **WHEN** 部署配置了子路径前缀后请求任一非 API 路径（含 SPA 深链）
- **THEN** 返回的 `index.html` 已注入指向该前缀的文档基址与运行时基址

#### Scenario: 静态资源原样返回
- **WHEN** 请求的是静态目录中真实存在的资源文件
- **THEN** 该文件原样返回，不注入任何内容

#### Scenario: 静态解析限定在静态目录内
- **WHEN** 请求路径包含 `..` 等试图逃出静态目录的片段
- **THEN** 系统不返回静态目录之外的文件（回退为 `index.html` 或 404），不得泄露源码等目录外内容

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

### Requirement: Document Path Lookup
`GET /api/documents` SHALL 支持可选 `path` 查询参数,提供时仅返回该精确路径的文档(等值匹配,非模糊);可与 `node_id` / `rag_status` 组合。

#### Scenario: 按 path 精确定位
- **WHEN** 客户端调用 `GET /api/documents?node_id=<节点>&path=docs/a.md`
- **THEN** 返回该 (节点, 路径) 下的单条文档(含 `id`);未命中返回 `[]`
