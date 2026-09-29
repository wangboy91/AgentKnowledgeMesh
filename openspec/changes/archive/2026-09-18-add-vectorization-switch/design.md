# add-vectorization-switch · 设计

## Context

现状(本变更前):

- `app_settings` 只有 `rag_sync_mode`(`auto`/`manual`,默认 `auto`),由 `services/rag/sync.py` 读写
- 三处入库通道各自决定初始状态:`services/indexer.py::sync_documents`(本地扫描)、`api/nodes.py::_sync_node_documents`(节点上传)、`api/documents.py`(创建/更新),判断式重复写着 `"indexed" if rag_mode == "auto" else "excluded"`
- `rag_status` 三态:`indexed` / `pending` / `excluded`;`_excluded_ids()` 以 `rag_status != "indexed"` 作为语义检索排除集
- `main.py` 启动时无条件 `init_table()`(失败仅告警);`vector_store.get_conn()` 懒连接
- `POST /api/rag/index` 同步遍历非 `excluded` 文档嵌入,**不回写 `rag_status`**

约束:

- 无 schema 迁移机制(启动 `create_all` + 手写加列),新增状态值不能依赖 DDL 变更 → `rag_status` 是 TEXT,直接扩取值即可
- `init_table()` 阻塞(psycopg2 + 嵌入维度探测),在异步上下文须走线程池
- 设置读写在请求会话内完成;启动时读设置需在 `init_db()` 之后

## Goals / Non-Goals

**Goals:**

- 向量化能力**默认整体关闭**:不初始化向量库、不产生任何嵌入调用、语义检索端点可用(降级为关键词)而非报错
- 开启后,文档是否向量化由用户**手动**决定;自动向量化成为「总开关开启 + auto 模式」这一显式组合下的行为
- 区分「尚未向量化」(`not_indexed`)与「用户显式移出」(`excluded`)
- 保持既有的统一索引通道(`services/rag/sync.py`)、节点上传协议、勾选端点契约不变

**Non-Goals:**

- 不做逐文档的向量化进度/任务队列(现有"后台派发 + 状态回写"足够,失败仅告警)
- 不改嵌入供应商与向量库选型、不改分块与混合检索算法
- 不做定时/增量自动向量化(全量索引仍是手动触发的唯一批量入口)
- 不为存量已 `indexed` 文档做向量清理(重新开启即复用,清理属用户主动「移出 RAG」)

## Decisions

### D1: 开关落在 `app_settings`,不进环境变量

`vectorization_enabled` 与 `rag_sync_mode` 同源,持久化在 `app_settings`(`"true"`/`"false"` 文本),缺省视为 `false`。

- 备选:环境变量 `AKM_VECTORIZATION_ENABLED` —— 运行时切换需要重启容器,与"设置页开关"的产品形态冲突;且两个来源叠加会出现"env 开了但 UI 显示关"的解释成本
- 依据:与既有 `rag_sync_mode` 的存储与读写方式完全一致,零新机制

### D2: 状态策略收敛为单一函数,三个入库通道共用

在 `services/rag/sync.py` 增加:

```python
def initial_rag_status(rag_mode: str, vectorization_enabled: bool) -> str:
    """仅「总开关开启 + auto」自动向量化,其余一律未向量化。"""
    return "indexed" if (vectorization_enabled and rag_mode == "auto") else "not_indexed"

def should_auto_index(rag_mode: str, vectorization_enabled: bool) -> bool:
    return vectorization_enabled and rag_mode == "auto"
```

`sync_documents` / `_sync_node_documents` / 文档创建更新一律调用它,消除重复判断式。

- 备选:保持各处 `if/else` 手写 —— 四态 × 两个开关的分支扩散,必然漂移
- 备选:引入"策略对象"——当前只有两个输入,过度设计

### D3: 关闭时语义检索**降级为关键词**,而不是报错

`/api/rag/search`、`/api/rag/context` 在关闭时用 `title/path/content ILIKE` 检索并返回**同形响应**(`results[].score` 取命中权重、`chunk` 取匹配片段),额外带 `"mode": "keyword"` 供调用方判断。

- 依据:节点本地 MCP 代理与外部 Agent 都把这两个端点当"检索入口"用,关闭向量化后返回 409/500 会让调用方直接失败;降级为关键词保证"入口永远可用",与 §9.3「不做第二检索引擎」的定位一致
- 备选:返回 409 提示未开启 —— 调用方需自行改调 `/api/search`,破坏"一个检索入口"的封装
- 备选:仍连向量库、只是不新增 —— 未配 pgvector 的部署每次检索都要先失败一次,违背"关闭 = 不碰向量子系统"

### D4: 开启总开关时同步初始化向量库,失败即拒绝

`PUT /api/settings` 把 `vectorization_enabled` 由 `false` 置 `true` 时,先在 `asyncio.to_thread` 中执行 `init_table()`;成功才落库并返回,失败返回 500 且**保持关闭**。

- 依据:让"开了但不可用"这一状态不可能出现;向量库/嵌入配置错误在开启瞬间就暴露,而不是等到第一次检索
- 备选:先落库、后台初始化 —— 用户看到开关已开但功能时好时坏,排障困难
- 关闭方向(`true → false`)不做任何清理:不删向量、不关连接,重新开启立即恢复

### D5: 「进入 auto+开启组合」时后台补齐 `not_indexed`

`rag_sync_mode` 切到 `auto`、或开启总开关导致最终状态为「开启 + auto」时,后台把 `rag_status != "excluded"` 且有内容的文档排队向量化(状态置 `pending` → 完成后 `indexed`)。

- 与 `POST /api/rag/index` 共用同一实现(`sync_index_and_mark(..., pending=True)`),避免两套补齐逻辑
- 备选:开启开关时不动存量,等用户手动全量索引 —— 与"auto 模式"的语义自相矛盾

### D6: `POST /api/rag/index` 改为后台派发并回写状态

现状同步遍历嵌入(大库会超时)且不回写状态,导致 `not_indexed` 文档即使嵌入成功仍不被语义检索召回。改为:收集非 `excluded` 且有内容的文档 → 后台统一通道(带 `pending`)→ 返回 `{"message", "queued"}`。

- **不返回 `total_chunks`**:该值需调用 `vector_store.get_stats()`,而 psycopg2 是同步驱动、向量库可能是远端主机,放在请求路径上会把响应拖住(实测本机 `.env` 指向远端 PG 时该调用长时间不返回);分块总数由 `GET /api/rag/stats` 提供,Web 端本就单独取用
- 同时把 `/api/rag/stats` 的 `get_stats()` 放入线程池,避免阻塞事件循环
- 契约变更:`indexed` 字段改名 `queued`(语义更准确)。`docs/api-reference.md` 与 Web 同步更新
- 备选:保留同步返回真实嵌入数 —— 数百篇文档时请求必然超时

### D7: 关闭时「加入 RAG」拒绝、「移出 RAG」放行

关闭状态下 `PUT /api/documents/{id}/rag` / `POST /api/documents/rag/batch` 的 `enabled=true` 返回 409(无可向量化目标,静默无操作会误导);`enabled=false` 仍放行(置 `excluded` + 清向量,属无副作用的清理)。

- 依据:关闭期间用户仍可能想预先标记"这篇不要进 RAG",而"加入"在没有向量化能力时无意义

## Risks / Trade-offs

- [升级后默认行为变化,老用户以为语义检索坏了] → README 使用说明、发布说明显著标注;设置页在关闭态给出"开启向量化"引导文案;`/api/rag/stats` 暴露 `vectorization_enabled` 供前端判断
- [`/api/rag/index` 响应字段改名破坏既有脚本] → 该端点原为同步全量重建、调用方极少(Web 与文档);在 `docs/api-reference.md` 标注变更,并保留 `total_chunks`
- [关闭期间 MCP/Agent 拿到关键词结果却以为在走语义] → 响应显式带 `"mode": "keyword"`;MCP 文本输出首行标注"关键词检索(向量化未开启)"
- [存量 `indexed` 文档在关闭期间"状态显示已索引但检索不到"] → 属预期(整体降级);设置页关闭态文案说明,重新开启即恢复
- [开启时 `init_table()` 阻塞请求] → 走 `asyncio.to_thread`;`init_table` 本身有幂等短路(`_table_ready`)与维度一致时不重建

## Migration Plan

1. 部署升级后首次启动:读取 `vectorization_enabled`(无记录 → `false`)→ 跳过 `init_table()` 并打印提示;`rag_sync_mode` 无记录 → `manual`
2. 存量文档 `rag_status` 不动(`indexed` 保持 `indexed`),向量表不动
3. 需要语义检索的部署:设置页开启向量化 → `init_table()` 通过 → 如需自动入库再把模式切 `auto`(触发后台补齐),否则手动勾选/全量索引
4. 回滚 = 回退版本;`app_settings` 中多出的键对旧版本无影响

## Open Questions

(无)
