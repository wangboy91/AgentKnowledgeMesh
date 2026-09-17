# knowledge-indexing 能力规格

## Purpose

递归扫描本地 Markdown 知识库目录并增量索引到 SQLite/PostgreSQL 可切换存储，为搜索、浏览与 AI 集成提供文档数据底座。

## Requirements

### Requirement: Markdown Directory Scanning
系统 SHALL 递归扫描所有已配置知识库目录中的 Markdown 文件，提取元信息（相对路径、标题、SHA256 哈希、大小、全文），并跳过不符合规则的文件。

#### Scenario: 递归扫描并收集文档
- **WHEN** 触发扫描且知识库目录包含嵌套的 `.md` 文件
- **THEN** 系统递归发现所有 `.md` 文件，每个文档记录相对路径（如 `projects/ai-crm.md`）、标题、SHA256 哈希、字节大小和全文内容

#### Scenario: 跳过隐藏文件与目录
- **WHEN** 路径中任一层级以 `.` 开头（如 `.obsidian/note.md`）
- **THEN** 该文件不进入扫描结果

#### Scenario: 跳过超大文件
- **WHEN** 文件大小超过 `AKM_MAX_FILE_SIZE_MB`（默认 10MB）
- **THEN** 该文件不进入扫描结果

#### Scenario: 跳过不可读文件
- **WHEN** 文件无法以 UTF-8 解码或无读取权限
- **THEN** 该文件被静默跳过，不中断整体扫描

### Requirement: Multiple Knowledge Roots
系统 SHALL 支持通过 `AKM_KNOWLEDGE_ROOTS` 配置多个知识库目录（逗号分隔），未配置时回退到默认目录。

#### Scenario: 多目录扫描加来源前缀
- **WHEN** 配置了多个知识库目录
- **THEN** 每个文档的相对路径以所在目录名为前缀（如 `obsidian-doc/projects/ai.md`），避免不同目录间路径冲突

#### Scenario: 默认知识库目录
- **WHEN** 未配置 `AKM_KNOWLEDGE_ROOTS`
- **THEN** 系统使用 `~/Knowledge` 作为知识库目录（Hub 端不存在时自动创建）

#### Scenario: 忽略不存在的目录
- **WHEN** 配置列表中包含不存在的路径
- **THEN** 该路径被忽略，仅扫描实际存在的目录

### Requirement: Title Extraction
系统 SHALL 从文档内容提取标题：优先使用首个 `# ` 开头的行，否则回退到文件名。

#### Scenario: 从一级标题提取
- **WHEN** 文档内容中存在以 `# ` 开头的行
- **THEN** 标题取该行 `# ` 之后的文本（去除首尾空白）

#### Scenario: 回退到文件名
- **WHEN** 文档没有 `# ` 标题行
- **THEN** 标题取文件名（去 `.md` 扩展名，下划线与连字符替换为空格）

### Requirement: Incremental Index Sync
系统 SHALL 基于路径匹配与 SHA256 哈希对比执行增量索引：新增文档插入、内容变化更新、文件消失删除，并返回同步统计。

#### Scenario: 新文档入库
- **WHEN** 扫描结果中出现索引中不存在的路径
- **THEN** 系统创建索引记录（路径唯一性按 `(node_id, path)` 约束），统计 `created` 计数加一

#### Scenario: 内容变化触发更新
- **WHEN** 已索引路径的 SHA256 哈希与扫描结果不同
- **THEN** 系统更新该记录的标题、哈希、大小与内容，统计 `updated` 计数加一

#### Scenario: 消失文件清理
- **WHEN** 已索引路径未出现在本次扫描结果中
- **THEN** 系统删除该索引记录，统计 `deleted` 计数为其数量

### Requirement: Scan Trigger API
系统 SHALL 提供 `POST /api/documents/scan` 端点,触发全量扫描与增量索引同步;**auto 模式下,对本次产生的新增/更新文档 SHALL 在响应后派发后台向量同步;manual 模式下 SHALL NOT 产生任何向量操作。**

#### Scenario: 扫描完成返回统计
- **WHEN** 客户端调用 `POST /api/documents/scan`
- **THEN** 系统执行扫描与同步,返回 `{"message": "Scan completed", "created": N, "updated": N, "deleted": N}`

#### Scenario: auto 模式扫描后自动向量化
- **WHEN** RAG 模式为 `auto` 且本次扫描产生了 created/updated 文档
- **THEN** 系统在返回统计后,于后台对新/变更文档分块、嵌入并写入向量表(向量失败仅告警)

#### Scenario: manual 模式扫描不产生向量
- **WHEN** RAG 模式为 `manual` 且本次扫描产生了 created/updated 文档
- **THEN** 这些文档 `rag_status` 为 `excluded`,无任何向量操作

### Requirement: Switchable Database Storage
系统 SHALL 支持通过 `AKM_DB_TYPE` 在 SQLite（默认）与 PostgreSQL 之间切换文档索引存储，所有配置项以 `AKM_` 为环境变量前缀。

#### Scenario: SQLite 默认存储
- **WHEN** 未配置数据库类型
- **THEN** 系统使用 SQLite，数据库文件默认位于项目 `data/` 目录下，目录不存在时自动创建

#### Scenario: PostgreSQL 切换
- **WHEN** 配置 `AKM_DB_TYPE=postgres` 及连接参数（`AKM_DB_HOST`/`AKM_DB_PORT`/`AKM_DB_NAME`/`AKM_DB_USER`/`AKM_DB_PASSWORD`）
- **THEN** 系统使用 asyncpg 连接 PostgreSQL 存储索引

### Requirement: Document Data Model
文档索引记录 SHALL 包含：自增主键、节点标识（本地文档默认 `local`）、路径、标题、SHA256 哈希、字节大小、标签（JSON 数组）、全文内容、创建与更新时间，且 `(node_id, path)` 组合唯一。

#### Scenario: 本地文档默认节点标识
- **WHEN** Hub 本地扫描创建文档记录
- **THEN** 记录的 `node_id` 为 `local`

#### Scenario: 同节点路径唯一
- **WHEN** 同一节点下出现重复路径的文档
- **THEN** 唯一约束 `(node_id, path)` 阻止重复记录
