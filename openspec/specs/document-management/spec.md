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
系统 SHALL 提供 `POST /api/documents` 端点，接收 `path`、`title`、`content` 创建新文档。

#### Scenario: 创建成功
- **WHEN** 客户端提交不冲突路径的文档
- **THEN** 系统计算 SHA256 哈希与字节大小并入库，尽力同步向量索引，返回完整文档记录

#### Scenario: 路径冲突
- **WHEN** 提交路径与现有文档重复
- **THEN** 系统返回 409，`detail` 为 "Document already exists at this path"

#### Scenario: 标题缺省时自动提取
- **WHEN** 未提供标题或标题为空
- **THEN** 系统依次尝试从内容前 5 行中提取 `# ` 标题，否则使用路径文件名（去扩展名）

### Requirement: Document Update
系统 SHALL 提供 `PUT /api/documents/{doc_id}` 端点，接收 `content` 更新文档正文。

#### Scenario: 更新正文并重算元信息
- **WHEN** 客户端提交新内容
- **THEN** 系统更新内容、重算 SHA256 哈希与字节大小，并在内容前 5 行存在 `# ` 标题时更新标题

#### Scenario: 更新后同步向量索引
- **WHEN** 文档更新成功
- **THEN** 系统尽力更新该文档的向量索引；向量更新失败不影响文档更新结果

#### Scenario: 更新不存在的文档
- **WHEN** 客户端请求更新不存在的文档 ID
- **THEN** 系统返回 404

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
系统 SHALL 在生产模式下（存在前端构建产物时）托管静态资源，并对非 API 路径提供 SPA 路由回退。

#### Scenario: 前端路由回退
- **WHEN** 请求的非 API 路径在静态目录中没有对应文件
- **THEN** 系统返回 `index.html`，由前端路由接管

### Requirement: Document RAG Status Visibility
文档列表与详情 SHALL 携带 `rag_status` 字段;文档列表 SHALL 支持按 `rag_status` 过滤(`GET /api/documents?rag_status=excluded` 等)。

#### Scenario: 列表携带状态
- **WHEN** 客户端调用 `GET /api/documents`
- **THEN** 每项包含 `rag_status` 字段

#### Scenario: 按状态过滤
- **WHEN** 客户端调用 `GET /api/documents?rag_status=excluded`
- **THEN** 仅返回 `rag_status` 为 `excluded` 的文档

### Requirement: Document Path Lookup
`GET /api/documents` SHALL 支持可选 `path` 查询参数,提供时仅返回该精确路径的文档(等值匹配,非模糊);可与 `node_id` / `rag_status` 组合。

#### Scenario: 按 path 精确定位
- **WHEN** 客户端调用 `GET /api/documents?node_id=<节点>&path=docs/a.md`
- **THEN** 返回该 (节点, 路径) 下的单条文档(含 `id`);未命中返回 `[]`
