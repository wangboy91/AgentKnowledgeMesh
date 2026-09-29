# vector-search 能力规格

## Purpose

将文档向量化存储于 PostgreSQL + pgvector，提供语义搜索与 RAG 上下文组装，补充关键词搜索的语义级检索能力。

## Requirements

### Requirement: Markdown-Aware Chunking
系统 SHALL 在向量化前按 token 计数将文档分块，并保持 Markdown 结构完整性：按标题层级切分，表格与代码块不跨块切碎，每个 chunk 前置其所属标题作为上下文。

#### Scenario: 标题层级分块
- **WHEN** 文档包含多级 Markdown 标题
- **THEN** 系统按标题层级切分，各级标题下内容作为独立 chunk，而非仅按固定长度硬切

#### Scenario: 表格与代码块不切碎
- **WHEN** 文档包含 Markdown 表格或代码块
- **THEN** 系统分块时不将表格或代码块从中间切断，整块保留在同一个 chunk 中

#### Scenario: 标题前置上下文
- **WHEN** 系统生成文档 chunk
- **THEN** 每个 chunk 的内容前置其所属标题路径（如 `## 章节名`），使向量携带结构上下文

#### Scenario: token 计数分块
- **WHEN** 文档 token 数超过分块上限
- **THEN** 系统以 token（而非字符）度量块大小，接近上限时在断句点切分，块间保留重叠

#### Scenario: 短文档单块
- **WHEN** 文档 token 数不超过分块上限
- **THEN** 整篇文档作为单个 chunk 返回

### Requirement: Semantic Search Endpoint
系统 SHALL 提供 `GET /api/rag/search` 端点,基于向量相似度与关键词匹配进行混合检索,以 RRF 融合两侧结果,并返回满足相似度阈值的相关分块(同一文档可返回多个分块)。**检索 SHALL 仅召回 `rag_status` 为 `indexed` 的文档;向量化关闭时 SHALL 降级为关键词检索并标注 `"mode": "keyword"`。**

#### Scenario: 语义检索
- **WHEN** 客户端调用 `GET /api/rag/search?q=<查询文本>`
- **THEN** 系统分别执行向量检索与关键词匹配,融合后按相关度排序返回 `{"query", "count", "results": [{"doc_id", "title", "path", "node_id", "chunk", "score"}]}`,limit 范围 1–20(默认 5),支持 `node_id` 过滤

#### Scenario: 同文档只保留最佳分块
- **WHEN** 同一文档的多个分块均与查询相关
- **THEN** 系统返回该文档的多个最佳分块(每文档有数量上限),而非仅保留一个分块

#### Scenario: 相似度阈值过滤
- **WHEN** 检索候选中存在相似度低于阈值的项
- **THEN** 系统不返回这些低于阈值的候选,而非无条件凑满 limit

#### Scenario: 关键词精确命中
- **WHEN** 查询包含文件名、ID 或专有名词等精确词项
- **THEN** 关键词匹配确保这些精确命中进入融合候选,弥补纯向量检索的漏检

#### Scenario: 排除文档不召回
- **WHEN** 某文档 `rag_status` 为 `excluded`(或尚未 `indexed`)
- **THEN** 无论其内容与查询多相关,均不出现在检索与 RAG 上下文结果中

#### Scenario: 向量化关闭时降级
- **WHEN** `vectorization_enabled` 为 `false`
- **THEN** 系统以关键词匹配(标题/路径/内容)构造同形结果返回,响应含 `"mode": "keyword"`,不访问向量库

#### Scenario: 检索失败降级
- **WHEN** 向量检索过程发生异常(如数据库不可用)
- **THEN** 系统返回 `{"query", "count": 0, "results": [], "error": <信息>}`,不抛出 500

### Requirement: RAG Context Assembly
系统 SHALL 提供 `GET /api/rag/context` 端点，返回语义相关文档的完整内容，用于 RAG prompt 组装。**向量化关闭时 SHALL 降级为关键词检索并标注 `"mode": "keyword"`。**

#### Scenario: 组装上下文
- **WHEN** 客户端调用 `GET /api/rag/context?q=<查询文本>`
- **THEN** 系统先语义检索（limit 范围 1–10、默认 3，支持 `node_id` 过滤），再按检索顺序取回全文，返回每篇文档的 title、content、path、node_id、score 与 matched_chunk

#### Scenario: 向量化关闭时降级
- **WHEN** `vectorization_enabled` 为 `false`
- **THEN** 系统以关键词匹配取回文档全文,响应含 `"mode": "keyword"`,不访问向量库

#### Scenario: 无检索结果
- **WHEN** 语义检索无命中
- **THEN** 返回 `{"query", "count": 0, "documents": []}`

#### Scenario: 组装失败降级
- **WHEN** 组装过程发生异常
- **THEN** 系统返回 count 0 与 error 信息，不抛出 500

### Requirement: Vector Index Management
系统 SHALL 提供 `POST /api/rag/index` 端点,将数据库中有内容的文档向量化入库(**`rag_status` 为 `excluded` 的文档 SHALL 被跳过**);**仅「向量化总开关开启 + `rag_sync_mode=auto`」时文档增删改才自动同步向量索引**,触发路径包括文档 API 的创建/更新/删除、节点文档推送的增量入库与本地扫描的增量同步;其余情况仅显式操作产生向量操作。

#### Scenario: 全量索引
- **WHEN** 向量化开启且客户端调用 `POST /api/rag/index`
- **THEN** 系统遍历除 `excluded` 外的全部有内容文档(含 `not_indexed`/`pending`),后台分块、嵌入并写入向量表,完成后把 `pending` 回写 `indexed`,返回 `{"message", "queued": N}`

#### Scenario: 重复索引覆盖旧向量
- **WHEN** 对已索引文档再次入库
- **THEN** 系统先删除该文档的旧分块向量再写入新向量

#### Scenario: 文档生命周期同步
- **WHEN** 向量化开启且模式为 auto,文档经索引同步、文档 API 创建/更新/删除、节点文档推送或本地扫描被增量入库
- **THEN** 系统尽力同步向量索引(新增/覆盖/删除对应向量);向量操作失败仅记录告警,不影响主流程

#### Scenario: 手动模式无隐式向量操作
- **WHEN** 模式为 manual,或向量化总开关关闭
- **THEN** 节点上传或本地扫描产生的新文档不入库向量,直到该文档被显式"加入 RAG"或执行全量索引

#### Scenario: 关闭时全量索引被拒
- **WHEN** 向量化关闭且客户端调用 `POST /api/rag/index`
- **THEN** 系统返回 409,不执行任何嵌入

#### Scenario: 索引失败降级
- **WHEN** 全量索引过程发生异常
- **THEN** 系统返回 `{"message": "Index failed: ...", "queued": 0}`,不抛出 500

### Requirement: Vector Backfill
系统 SHALL 提供存量回填脚本，为已入库但向量表中缺失向量的文档补建向量；已存在向量的文档 SHALL NOT 被重复嵌入。

#### Scenario: 只补缺失向量
- **WHEN** 回填脚本执行时，数据库中存在向量表中没有对应分块的文档
- **THEN** 系统仅对这些文档分块、嵌入并写入向量表，跳过向量表中已存在的文档

#### Scenario: 回填输出统计
- **WHEN** 回填脚本执行完成
- **THEN** 脚本输出补建向量与跳过的文档数量统计

#### Scenario: 回填失败降级
- **WHEN** 单篇文档嵌入失败
- **THEN** 脚本记录告警并继续处理其余文档，最终统计中如实反映失败数量

### Requirement: Vector Storage Backend
向量存储 SHALL 使用 PostgreSQL + pgvector，表结构自动初始化，并在嵌入维度变化时自动重建。

#### Scenario: 懒初始化
- **WHEN** 首次使用向量功能
- **THEN** 系统确保 `vector` 扩展存在并创建向量表（默认表名 `document_vectors`，含 doc_id、标题、路径、node_id、分块序号、分块内容、embedding 列）及 doc_id 索引

#### Scenario: 维度自动检测
- **WHEN** 未显式配置 `AKM_VECTOR_DIMENSIONS`（值为 0）
- **THEN** 系统通过嵌入探测文本自动确定向量维度

#### Scenario: 嵌入模型切换后重建
- **WHEN** 现有向量表的嵌入维度与当前模型不一致
- **THEN** 系统删除并重建向量表（旧向量与新模型不兼容）

#### Scenario: 相似度索引按维度选择
- **WHEN** 初始化向量索引
- **THEN** 维度 ≤ 2000 时创建 HNSW 余弦相似度索引；更高维度使用 halfvec 表达式索引

#### Scenario: 向量库连接回退
- **WHEN** 未单独配置向量库连接参数
- **THEN** 向量库复用主数据库的连接配置（单一数据库部署）

### Requirement: Vector Stats Endpoint
系统 SHALL 提供 `GET /api/rag/stats` 端点，返回向量存储统计与向量化开关状态。

#### Scenario: 返回分块总数
- **WHEN** 客户端调用 `GET /api/rag/stats`
- **THEN** 系统返回 `{"total_chunks": N, "vectorization_enabled": <bool>}`；异常时返回 `{"total_chunks": 0, "error": ...}`

#### Scenario: 关闭时不连向量库
- **WHEN** 向量化处于关闭态
- **THEN** 系统返回 `{"total_chunks": 0, "vectorization_enabled": false}`,不建立向量库连接

### Requirement: Embedding Provider Configuration
系统 SHALL 支持通过 `AKM_EMBEDDING_PROVIDER` 切换嵌入供应商：`ark`（默认，火山引擎 Ark API，模型 `doubao-embedding-vision-250615`，需 `AKM_ARK_API_KEY`）或 `local`（本地 sentence-transformers）。

#### Scenario: 默认 Ark 供应商
- **WHEN** 未配置嵌入供应商
- **THEN** 系统使用火山引擎 Ark API 生成嵌入

#### Scenario: 本地嵌入切换
- **WHEN** 配置 `AKM_EMBEDDING_PROVIDER=local`
- **THEN** 系统使用本地 sentence-transformers 生成嵌入，无需外部 API

### Requirement: RAG Graceful Degradation
RAG 子系统故障 SHALL 不阻塞服务启动与核心文档功能。

#### Scenario: 启动时向量初始化失败
- **WHEN** 服务启动时向量表初始化失败（如无 PostgreSQL 连接）
- **THEN** 系统记录告警并继续启动，文档与搜索功能正常可用

#### Scenario: 文本分块
- **WHEN** 文档被向量化
- **THEN** 系统按 token 计数并保持 Markdown 结构分块（详见 Markdown-Aware Chunking），不超过上限的文本作为单块返回

### Requirement: Document-Level RAG Selection
系统 SHALL 为每篇文档维护 RAG 状态 `rag_status`(`not_indexed` / `pending` / `indexed` / `excluded`),并提供单篇与批量操作(admin):`PUT /api/documents/{doc_id}/rag`(body `{"enabled": bool}`)与 `POST /api/documents/rag/batch`(body `{"doc_ids": [...], "enabled": bool}`)。**`not_indexed` 表示尚未向量化(默认态),`excluded` 表示用户显式移出。**

#### Scenario: 手动加入 RAG
- **WHEN** 向量化开启且 admin 对 `not_indexed` 或 `excluded` 文档执行"加入 RAG"(单篇或批量)
- **THEN** 该文档标记 `pending` 并后台向量化,完成后转 `indexed`

#### Scenario: 移出 RAG 清理向量
- **WHEN** admin 对某文档执行"移出 RAG"
- **THEN** 该文档标记 `excluded` 并删除其全部分块向量

#### Scenario: 关闭时加入被拒
- **WHEN** 向量化关闭且 admin 执行"加入 RAG"(单篇或批量,`enabled=true`)
- **THEN** 系统返回 409 并提示需先开启向量化,文档状态不变

#### Scenario: 关闭时移出放行
- **WHEN** 向量化关闭且 admin 执行"移出 RAG"(`enabled=false`)
- **THEN** 系统正常将该文档置 `excluded` 并清理其向量分块

#### Scenario: 非管理员被拒
- **WHEN** viewer 调用文档 RAG 勾选端点
- **THEN** 返回 403

### Requirement: Vectorization Master Switch
系统 SHALL 维护全局设置 `vectorization_enabled`(向量化总开关,持久化于应用设置存储,**默认 `false`**),控制向量化子系统的整体启用状态。**关闭时系统 SHALL NOT 产生任何嵌入调用、SHALL NOT 初始化向量库(含启动阶段),语义检索端点 SHALL 降级为关键词检索而非报错。**

#### Scenario: 默认关闭
- **WHEN** 未配置 `vectorization_enabled`
- **THEN** 系统处于关闭态:启动时跳过向量表初始化并打印提示,服务照常启动

#### Scenario: 关闭时不初始化向量库
- **WHEN** 服务启动且向量化处于关闭态
- **THEN** 系统不连接向量库、不创建向量表、不执行嵌入维度探测;文档与关键词检索功能完全可用

#### Scenario: 开启时同步初始化
- **WHEN** admin 将 `vectorization_enabled` 由 `false` 置为 `true`
- **THEN** 系统先执行向量表初始化,成功后才持久化并返回成功;初始化失败返回 500 且开关保持关闭

#### Scenario: 关闭不清理既有向量
- **WHEN** admin 将 `vectorization_enabled` 由 `true` 置为 `false`
- **THEN** 系统仅持久化开关状态,不删除既有向量分块、不清空向量表;重新开启后既有向量立即可用

#### Scenario: 关闭时语义检索降级为关键词
- **WHEN** 向量化处于关闭态且客户端调用 `GET /api/rag/search` 或 `GET /api/rag/context`
- **THEN** 系统改用文档表关键词匹配(标题/路径/内容)返回**同形响应**,并在响应中标注 `"mode": "keyword"`;不连接向量库、不抛出 500

### Requirement: RAG Sync Mode and Defaults
系统 SHALL 维护全局设置 `rag_sync_mode`(`auto` 或 `manual`,**默认 `manual`**),持久化于应用设置存储并支持运行时切换;提供 `GET /api/settings`(viewer 可读)与 `PUT /api/settings`(仅 admin,支持 `rag_sync_mode` / `vectorization_enabled` 两项的**部分更新**,至少提供一项)。

#### Scenario: 默认手动模式
- **WHEN** 未配置 RAG 模式
- **THEN** 系统处于 `manual`:新/变更文档标记为 `not_indexed`,不产生向量操作

#### Scenario: 切换为手动
- **WHEN** admin 将模式切换为 `manual`
- **THEN** 此后新文档(节点上传或本地扫描)默认标记为 `not_indexed`,不产生向量操作;既有向量**不**被清除

#### Scenario: 切回自动补齐索引
- **WHEN** admin 将模式从 `manual` 切回 `auto`,且向量化总开关为开启
- **THEN** 系统将所有非 `excluded` 的文档补齐向量化(后台执行)

#### Scenario: 向量化关闭时切模式不补齐
- **WHEN** 向量化总开关为关闭且 admin 将模式切换为 `auto`
- **THEN** 系统仅持久化模式,不执行任何嵌入(待总开关开启时再补齐)

#### Scenario: 设置读取与部分更新
- **WHEN** 客户端调用 `GET /api/settings`
- **THEN** 返回 `{"rag_sync_mode": <mode>, "vectorization_enabled": <bool>}`

#### Scenario: 非法值被拒
- **WHEN** admin 提交非法 `rag_sync_mode` 值,或提交的更新体两项皆缺省
- **THEN** 系统返回 400,不修改任何设置

### Requirement: Manual Vectorization Entry Points
向量化开启后,文档是否进入向量库 SHALL 由用户显式操作决定;系统 SHALL 提供三条手动向量化路径:`POST /api/rag/index`(全量)、`PUT /api/documents/{doc_id}/rag`(单篇)、`POST /api/documents/rag/batch`(批量)。

#### Scenario: 全量手动向量化
- **WHEN** 向量化开启且客户端调用 `POST /api/rag/index`
- **THEN** 系统把所有 `rag_status != "excluded"` 且有内容的文档(含 `not_indexed` 与 `pending`)排队进入后台向量化,文档状态转 `pending`,嵌入完成后回写 `indexed`;响应为 `{"message", "queued": N, "total_chunks": M}`

#### Scenario: 关闭时全量索引被拒
- **WHEN** 向量化处于关闭态且客户端调用 `POST /api/rag/index`
- **THEN** 系统返回 409 并提示需先在设置中开启向量化,不执行任何嵌入

#### Scenario: 关闭时加入被拒、移出放行
- **WHEN** 向量化处于关闭态且 admin 调用文档级勾选端点
- **THEN** `enabled=true` 返回 409(无可向量化目标);`enabled=false` 正常执行(置 `excluded` 并清理该文档向量分块)

#### Scenario: 索引完成后状态可被召回
- **WHEN** 全量或勾选向量化完成
- **THEN** 对应文档 `rag_status` 为 `indexed`,可被语义检索与 RAG 上下文召回
