# Proposal: add-vectorization-switch

## Why

现状**默认自动向量化**:`rag_sync_mode` 默认 `auto`,节点上传与本地扫描的文档入库即触发嵌入。带来三个问题:

1. **默认即产生外部成本**——接入 Ark API 的部署在首次扫描时会对全量文档发起嵌入调用(时间与费用均不可预期),本地嵌入则直接拉起重模型
2. **无法整体关停**——`manual` 模式只解决"新文档是否自动入库",不解决"这台 Hub 到底要不要向量化能力";只要库里有向量,语义检索就会去连 PostgreSQL,没配向量库的部署每次检索都要先失败一次
3. **状态语义混淆**——manual 模式下新文档被标为 `excluded`,与"用户主动移出语义检索"共用一个值,导致"从没向量化"和"被排除"无法区分

目标:向量化**默认关闭**,需要时由 admin 显式开启;开启后由用户**手动**决定哪些文档向量化(沿用既有勾选/批量/全量索引入口)。

## What Changes

- 新增全局设置 `vectorization_enabled`(向量化总开关,持久化于 `app_settings`,**默认 `false`**);关闭时不产生任何嵌入调用、不初始化向量库、语义检索端点降级为关键词检索
- `rag_sync_mode` 默认值由 `auto` 改为 **`manual`**(向量化开启后,新文档仍需显式勾选才入库)
- 文档 RAG 状态由三态扩为四态,新增 **`not_indexed`**(尚未向量化,即默认态);`excluded` 收窄为"用户显式移出"。入库策略统一为:**仅「总开关开启 + auto 模式」自动向量化,其余一律 `not_indexed`**
- `GET/PUT /api/settings` 同时读写两项设置,支持部分更新;开启总开关时先初始化向量库,失败则拒绝开启(不落库)
- `POST /api/rag/index` 语义调整:向量化关闭时返回 409;开启时把**所有非 `excluded` 文档**(含 `not_indexed`/`pending`)纳入后台向量化并回写 `indexed`(修复现状"索引后状态未回写、语义检索仍召回不到"的缺口);改为后台派发,响应 `{message, queued, total_chunks}`
- 向量化关闭时:`POST /api/documents/scan`、文档创建/更新、节点上传一律置 `not_indexed` 且无向量操作;文档级「加入 RAG」返回 409(「移出」仍允许,用于清理)
- `GET /api/rag/search`、`/api/rag/context` 在关闭时降级为关键词检索,响应带 `"mode": "keyword"`;`GET /api/rag/stats` 返回 `vectorization_enabled` 且关闭时不连向量库;MCP `search_documents(mode=semantic)` 同样降级
- Web:设置页新增「向量化」总开关(含风险确认);文件树/文档状态展示与筛选增加 `not_indexed`;关闭时相关操作入口禁用并提示

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `vector-search`: 新增向量化总开关需求;`rag_sync_mode` 默认改 manual;`rag_status` 增加 `not_indexed`;全量索引纳入 `not_indexed` 并回写状态;关闭时语义检索降级为关键词
- `knowledge-indexing`: 扫描入库的初始 `rag_status` 由"总开关 + 模式"共同决定(仅 auto+开启才自动向量化)
- `document-management`: 文档创建/更新按同一策略设定状态;关闭时勾选端点行为
- `mcp-integration`: 语义模式在向量化关闭时降级为关键词并明示

## Impact

- **server**:`services/rag/sync.py`(开关读写 + 状态策略)、`services/indexer.py`、`api/{documents,nodes,rag,settings}.py`、`main.py`(启动按开关决定是否初始化向量库)、`services/mcp_server.py`
- **web**:`api/client.ts`、`pages/{Settings,Knowledge,Dashboard}.tsx`、`components/FileTree.tsx`、`i18n/{zh,en}.ts`
- **数据**:`app_settings` 新增键;`documents.rag_status` 取值扩展(TEXT 列,无 schema 迁移)。**存量 `indexed` 文档的向量保留不动**,但总开关默认关闭期间语义检索走关键词降级;重新开启后立即恢复
- **兼容(破坏性)**:升级后默认行为变化——不再自动向量化、语义检索默认不可用。需在 README 与发布说明中显著标注,并在设置页给出引导
