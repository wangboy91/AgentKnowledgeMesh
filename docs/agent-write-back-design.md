# 智能体写回(Agent Write-back)· 架构与实现设计

> 状态:**已实施、端到端验证通过、openspec 变更已归档**(`2026-09-29-add-mcp-write-tools`)。
> 日期:2026-09-29。本文是批次 3(见 §1.3)的设计输入,实施按 `docs/conventions/workflow.md` §2 走 openspec 变更 `add-mcp-write-tools`;delta 已合入 `openspec/specs/{mcp-integration,account-auth,document-management}`。
> 上游需求:多电脑知识共享(文档分散在多台机器,机间无法共享,各机智能体无法取用)。产品定位见 [product-overview.md](product-overview.md);批次 1 见 [node-realtime-sync-design.md](node-realtime-sync-design.md)。

## 1. 背景与范围

### 1.1 要解决的问题

现状:知识库对智能体是**只读**的。三种接入形态(Hub stdio / Hub SSE / 节点本地代理)只暴露 `search_documents`、`get_document`、`list_documents` 三个读工具;REST 的写端点(`POST /api/documents`、`PUT /api/documents/{doc_id}`)一律 `require_auth("admin")`,节点凭证被明确拒绝(`403 Node credentials are read-only`)。

结果是知识只在两个通道里流动:**人手工编辑**与**文件扫描器**。智能体读了一堆文档、得出一个结论、写出一段总结,这段总结无处安放——只能留在对话里,下一轮对话又从零开始。

目标:让智能体**把产出的知识写回知识库**。写回后走既有的节点同步 / 检索 / MCP 通道分发,其他电脑上的智能体立即检索得到。这是"读 → 加工 → 写回 → 别处读到"的闭环收口,也是多机共享痛点的最后一环。

**本批次不引入任何 LLM 依赖**:写什么内容由调用方(智能体)决定,AKM 只提供存储与通道。

### 1.2 现状基线(与本文相关)

| 环节 | 现状 | 位置 |
| --- | --- | --- |
| MCP 工具集 | 三个只读工具:`search_documents` / `get_document` / `list_documents` | `src/server/app/services/mcp_server.py`、`src/node/app/mcp_proxy.py` |
| MCP 接入形态 | Hub SSE(`GET /api/mcp/sse`)、Hub stdio、节点本地 stdio 代理 | `src/server/app/api/mcp.py`、`src/node/app/__main__.py` |
| 文档写端点 | `POST /api/documents`(create)、`PUT /api/documents/{doc_id}`(update),均 `require_auth("admin")` | `src/server/app/api/documents.py:178,234` |
| 鉴权依赖 | `require_auth(min_role, allow_node)`;节点凭证 `allow_node=False` → 403;`allow_node=True` 且 `min_role=="viewer"` → 放行 | `src/server/app/services/auth.py:147` |
| 节点凭证 | `Principal(kind="node", role="node", node_id=<节点 id>)`,来自 `Node.token` | `auth.py:106` |
| 文档唯一性 | 表约束 `UniqueConstraint("node_id", "path")`;但 REST create 查的是**全局** `Document.path` | `models/document.py:27`、`documents.py:243` |
| 节点上传通道 | `PUT /api/nodes/{node_id}/documents`,按 `(node_id, path)` 作用域增量入库 | `src/server/app/api/nodes.py:272` |
| MCP 输出格式 | 单源 `akm_shared.mcp_formatting`,三形态共用 | `src/shared/akm_shared/mcp_formatting.py` |

**核心缺口**:全仓无任何"MCP → 写"的路径;节点凭证被硬编码为只读;REST create 的唯一性口径与 DB 约束、与节点同步协议三者不一致。

### 1.3 批次定位与本文范围

多机共享痛点的最短路径是「批次 1 → 批次 3」——批次 1 让变更**实时到达** Hub,批次 3 让智能体**能够产生**变更:

| 批次 | 内容 | 与本文关系 |
| --- | --- | --- |
| 1 | 节点文件监听 + 服务化 | 已完成(变更 `add-node-file-watch`);本变更的**上游** |
| 2 | wiki 页数据模型(`doc_type` / `derived_from` / stale) | 后续,LLM wiki 线 |
| **3** | **MCP 写工具(智能体可写回)** | **本文覆盖** |
| 4 / 5 | 可插拔 distiller / 自动化治理 | 后续,首个 LLM 依赖 |

**本文做**:MCP 新增 `create_document` / `update_document` 两个写工具(三形态一致);REST 写端点放行节点凭证但**作用域限 `principal.node_id`**;写入口径(标题 / hash / RAG 状态)抽为单源,供 REST 与 MCP 共用;统一文档唯一性为 `(node_id, path)`。

**本文不做**(明确划出,避免范围蔓延):

- **`delete_document`**——删除风险高,且不属"作者"语义;留给批次 5 的自动化治理(需要审计与回收站设计)
- **wiki 页数据模型**(`doc_type` / `derived_from` / stale 标记)——批次 2
- **服务端 distiller / 任何生成式 LLM 调用**——批次 4
- **Hub 侧反向下发**(节点拉取其他机器的文档)——未排期;本变更仍只解决"写上去",不解决"拉下来"
- **写操作审计日志**——留给治理批次
- **按路径 upsert**(`write_document(path)` 单工具语义)——本文坚持 create / update 分离,语义显式;若后续实际使用中反复出现"不知道 id 只想覆盖"的诉求,再评估

## 2. 目标架构

### 2.1 写回闭环

```
智能体(电脑 B)                     Hub                       智能体(电脑 A)
   |                                |                              |
   |-- search_documents ----------->|                              |
   |<-- 语料 -----------------------|                              |
   |   (本地加工,产生新知识)         |                              |
   |-- create_document ------------->|                              |
   |   (path, content)              |-- 入库(node_id = B)          |
   |                                |-- 后台向量维护(若开启)         |
   |                                |                              |
   |                                |<-- search_documents ---------|
   |                                |--- 命中刚写入的文档 --------->|
```

关键点:**写回与同步走同一条存储通道**——写回产出的是普通 `Document`(归属调用者节点),因此自动被文档树、关键词 / 语义检索、MCP 读工具、多机分发全部覆盖,零额外改造。

### 2.2 三形态位置

写工具在三种接入形态下**同名同参同输出**:

```
Hub stdio (akm-hub --mcp)      直连 DB,本地信任        → mcp_server.py 直接落库
Hub SSE  (GET /api/mcp/sse)    经 JWT 鉴权            → mcp_server.py 直接落库
节点代理 (akm-node --mcp)      经节点凭证转发 Hub REST → mcp_proxy.py → REST
```

Hub 两形态共享同一个 `mcp_server.py` 处理器;节点代理走 HTTP,因此**REST 必须先具备等价的写端点**。这是本设计的排序原则:**REST 是契约,MCP 工具是其薄封装**(Hub 形态为省一次回环直连 DB,但业务口径必须与 REST 逐字一致)。

### 2.3 权限模型

现状 `require_auth` 对节点凭证只有"全拒"与"放行只读"两态,写端点无处安放"节点可写"。本变更引入**第三态**:

| 调用者 | 读端点 | 写端点(本变更后) |
| --- | --- | --- |
| 无凭证 | 401 | 401 |
| viewer JWT | 200 | 403 |
| admin JWT | 200 | 200(作用域不限) |
| API Token(viewer 角色) | 200 | 403 |
| **节点 token** | 200(既有) | **200,但作用域限本节点** |

"作用域限本节点"的落点:

- **create**:节点凭证创建时 `node_id` **强制**为 `principal.node_id`(不接受调用方指定),杜绝冒充其他节点
- **update**:节点凭证只能更新 `doc.node_id == principal.node_id` 的文档,否则 `403`

作用域校验放在**端点业务层**而非 `require_auth`——`require_auth` 只负责"凭证类型 + 角色是否放行",它拿不到目标文档,无从判断作用域。

## 3. 详细设计

### 3.1 MCP 工具契约

新增两个工具,`inputSchema` 与描述在 `mcp_server.py` 与 `mcp_proxy.py` **两侧逐字一致**(与现有三工具同样的人工同步约束,注释已标注)。

**`create_document`**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 文档相对路径,如 `notes/foo.md` |
| `content` | string | 是 | Markdown 全文 |
| `title` | string | 否 | 标题;缺省或空时从内容前 5 行 `# ` 提取,再退化为路径文件名 |

**`update_document`**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `document_id` | integer | 是 | 文档 ID(由 `search_documents` / `list_documents` 获得) |
| `content` | string | 是 | 新的 Markdown 全文 |

**为什么 `update` 用 `document_id` 而非 `path`**:与既有 `get_document(document_id)` 词汇一致,且与 REST `PUT /api/documents/{doc_id}` 一一对应,节点代理可零歧义转发。代价是智能体跨会话需先检索拿 id——这正是 `search_documents` 的用途,不算额外负担。

**返回**:纯文本结果(与既有三工具一致),含 `id`、`title`、`path`、`node_id`、大小、更新时间。创建 / 更新的成功结果文案由 `akm_shared.mcp_formatting` 单源提供。

### 3.2 REST 端点改动

**`POST /api/documents`**

```python
principal = Depends(require_auth("admin", node_write=True))
...
node_id = principal.node_id if principal.kind == "node" else "local"
# 唯一性检查改为 (node_id, path)
existing = await session.execute(
    select(Document).where(Document.node_id == node_id, Document.path == path)
)
if existing.scalar_one_or_none():
    raise HTTPException(409, "Document already exists at this path")
```

**`PUT /api/documents/{doc_id}`**

```python
principal = Depends(require_auth("admin", node_write=True))
...
doc = await session.get(Document, doc_id)
if not doc:
    raise HTTPException(404, "Document not found")
if principal.kind == "node" and doc.node_id != principal.node_id:
    raise HTTPException(403, "无权修改该文档:不属于本节点")
```

### 3.3 写入口径单源

现状 create / update 的业务口径(标题提取、SHA256、字节大小、`rag_status` 策略、commit / refresh)内联在 `api/documents.py`。Hub 形态的 MCP 处理器直连 DB,若不抽取就会复制一份——两处口径漂移会让"经 MCP 写的文档"与"经 REST 写的文档"在 hash / 标题 / rag_status 上不一致,是隐性 bug 温床。

抽取 `src/server/app/services/document_writer.py`:

```python
async def create_document(session, *, node_id, path, content, title=None) -> Document
async def update_document(session, doc, content) -> Document
```

- 内部完成:唯一性检查(create)、标题提取、hash / size 计算、`resolve_rag_status`、`commit` + `refresh`
- 冲突 / 不存在分别抛 `PathConflict` / 由调用方先行判断(update 的 404 在调用方,因需先取 doc 做作用域校验)
- **不做**权限与作用域校验(那是端点职责)
- 向量派发不由本模块做:调用方以 `doc.rag_status == "indexed"` 作为"应派发"的信号——该等式与 `should_auto_index(rag_mode, vectorization_enabled)` 等价(见 `rag/sync.py`),无需重复读设置

`api/documents.py` 与 `mcp_server.py` 双双改为调用它,`_upsert_payload` 等既有辅助保持不动。

### 3.4 唯一性与作用域

**唯一性从"全局 path"改为 `(node_id, path)`**,三处口径统一:

| 位置 | 变更前 | 变更后 |
| --- | --- | --- |
| DB 约束 | `UniqueConstraint("node_id", "path")` | 不变(本来就是它) |
| REST create | 查全局 `Document.path` | 查 `(node_id, path)` |
| 节点同步 | `(node_id, path)` 作用域 | 不变 |

**为什么必须改**:`notes/todo.md` 这类通用路径在 A、B 两台机器上同时存在是常态。节点同步协议早已按 `(node_id, path)` 共存,若 REST create 仍按全局唯一,则 B 机智能体想创建 `notes/todo.md` 会因 A 机同名文档而 409——写回功能在最常见的场景下直接不可用。

这是对 `document-management` 能力 `Document Creation` 的**契约变更**(原 409 场景措辞是"提交路径与现有文档重复"),须走 MODIFIED delta 并在 `api-reference.md` 标注。

**节点写入的归属**:`node_id = principal.node_id`。写回的文档因此出现在该节点的文档树分支下,与节点扫描上来的文档同域。若智能体同时把文件落到本地知识库目录,下次扫描会以相同 `(node_id, path)` 命中同一条记录并按 hash 收敛,不会产生重复。

### 3.5 节点代理转调

`mcp_proxy.py` 现仅有 `_hub_get`。新增写通道:

```python
async def _hub_write(method: str, path: str, json: dict) -> httpx.Response
async def _safe_hub_write(...)  # 连接 / 超时 / 401 映射,与 _safe_hub_get 对称
```

- `create_document` → `POST /api/documents`,body `{path, title, content}`
- `update_document` → `PUT /api/documents/{document_id}`,body `{content}`

节点凭证经 `Authorization: Bearer <node_token>` 携带,Hub 侧据此强制作用域——**代理不传递、也不允许覆盖 `node_id`**。

### 3.6 错误语义

MCP 工具的错误分两类,与既有工具一致:

- **业务性错误**(调用方能自行纠正):普通文本结果,`isError` 不置位
- **基础设施错误**(连接 / 超时 / 鉴权失效):`isError=True` + 可操作文案

| 情形 | 返回 |
| --- | --- |
| create 路径已存在 | `路径已存在:<path>(文档 ID <id>),请改用 update_document。` |
| create/update 越权(跨节点) | `无权写入该文档:节点凭证只能写本节点名下的文档。` |
| update 文档不存在 | `文档 ID <id> 不存在。` |
| 缺少必填参数 | `缺少参数: <name>`(既有约定) |
| Hub 不可达 / 超时 / 401 | 沿用既有文案(`无法连接 Hub(...)` / `Hub 响应超时(...)` / `节点凭证已失效...`),`isError=True` |

### 3.7 输出格式单源

`akm_shared.mcp_formatting` 新增:

```python
def format_document_created(doc: dict) -> str   # 已创建文档 [id] 标题 + 路径/节点/大小
def format_document_updated(doc: dict) -> str   # 已更新文档 [id] 标题 + 路径/节点/大小/更新时间
```

Hub MCP 与节点代理共用,保证三形态输出逐字一致。

## 4. 配置项

**无新增配置项**。写能力由权限模型天然约束(admin 与节点凭证),不需要开关:

- 若部署方不希望智能体写回,不给节点配 MCP 代理、或用 viewer 级 API Token 接入即可
- 向量化行为沿用既有总开关与 `rag_sync_mode`(写回文档的 `rag_status` 走同一策略)

## 5. 兼容性与边界

- **协议向后兼容**:MCP 新增工具是纯增量,老客户端不感知;REST 端点路径与请求体不变,仅鉴权放宽与唯一性口径调整
- **唯一性口径变更的影响面**:仅当"同名路径已存在于**其他** `node_id` 下"时,行为由 409 变为 200(成功创建本节点下的同名文档)。这是**放宽**,不会让原本成功的请求失败
- **节点凭证写入的爆炸半径**:节点只能写 `node_id == principal.node_id` 的文档。**不能**删除、不能改别人的、不能改 `local`
- **`excluded` 粘性不变**:用户显式移出 RAG 的文档被智能体更新后仍是 `excluded`(`resolve_rag_status` 保证)
- **已知限制**:
  - 写回不落本地磁盘——文档只存在于 Hub DB,节点侧文件系统无对应文件。若智能体希望本地也有,需自行写文件;
    但注意(2026-09-30 起)该路径已被写回文档占用(`origin=agent`),**磁盘文件不会夺回它**——
    扫描/同步会跳过该条目并计入 `skipped`(见 [known-issues.md](known-issues.md) 问题 1/2 的修复)
  - 无并发写保护:两个智能体同时更新同一文档时后写覆盖先写(与现有 REST 行为一致)。冲突检测留待治理批次
  - 无删除能力,误写内容只能靠 update 覆盖;`agent` 来源文档也没有任何删除入口(文件事件对它免疫),只能长期保留

## 6. 验证口径

**单测**(`src/server/tests/`、`src/node/tests/`):

- 权限矩阵:节点凭证可 create / update 本节点文档;跨节点 update → 403;节点凭证仍不能改 `local` 文档
- 唯一性:`(node_id, path)` 相同 → 409;不同 node 的同名 path → 200
- 写入口径单源:REST 与 MCP 写入同一内容,hash / size / title / rag_status 完全一致
- MCP 工具:成功输出文案、409 / 403 / 404 文案、缺参数文案
- 节点代理:`_hub_write` 转调正确(方法 / 路径 / body)、错误状态码映射、401 文案
- 回归:既有读工具与 RAG 策略测试全绿

**实测**(Hub + 节点代理):

1. 经节点代理 `create_document` 写一篇新文档 → Hub 文档树出现该节点下的新条目
2. `search_documents` 能检索到刚写入的内容(关键词;若开启向量化则语义亦可)
3. `update_document` 覆盖正文 → Hub 端 `updated_at` 更新、hash 变化
4. 用 A 节点凭证 update B 节点文档 → 403 文案
5. `create_document` 重复路径 → 409 文案
6. 另一台机器的智能体经其自身代理检索 → 命中该文档(闭环验证)

**回归**:`src/server` 与 `src/node` 既有 pytest 全绿。

## 7. 待决与后续

- **`delete_document`**:需要审计与回收站,归批次 5 治理
- **写操作来源标记**(区分智能体写入 / 人工编辑 / 扫描)——批次 2 的 `doc_type` / `derived_from` 天然承载,届时一并设计
- **并发写冲突检测**(乐观锁 / `If-Match`):实际出现冲突诉求时再评估
- **Hub 反向下发**:节点只能推不能拉;写回的文档要"出现在本地磁盘"仍需未排期的下发能力
- **按路径 upsert**:若"不知道 id 只想覆盖"成为高频诉求,评估增加 `path` 版更新工具
