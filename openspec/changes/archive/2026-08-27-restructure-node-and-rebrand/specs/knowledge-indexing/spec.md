## MODIFIED Requirements

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

### Requirement: Switchable Database Storage
系统 SHALL 支持通过 `AKM_DB_TYPE` 在 SQLite（默认）与 PostgreSQL 之间切换文档索引存储，所有配置项以 `AKM_` 为环境变量前缀（历史 `AV_` 前缀作为弃用别名继续兼容）。

#### Scenario: SQLite 默认存储
- **WHEN** 未配置数据库类型
- **THEN** 系统使用 SQLite，数据库文件默认位于项目 `data/` 目录下，目录不存在时自动创建

#### Scenario: PostgreSQL 切换
- **WHEN** 配置 `AKM_DB_TYPE=postgres` 及连接参数（`AKM_DB_HOST`/`AKM_DB_PORT`/`AKM_DB_NAME`/`AKM_DB_USER`/`AKM_DB_PASSWORD`）
- **THEN** 系统使用 asyncpg 连接 PostgreSQL 存储索引
