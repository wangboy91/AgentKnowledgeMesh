# doc-viewer-header · 设计

## 背景

`MarkdownViewer` 的头部由三块组成,信息有重叠:

```
[面包屑]  AgentKnowledgeMesh / openspec / specs / document-conversion / spec.md
[h1]      document-conversion 能力规格
[meta]    📄 <完整 path>(截断)  · 2.4 KB · 🕐 时间 · RAG 状态
[正文]    # document-conversion 能力规格   ← 与 h1 同一个标题
```

`document.title` 的来源是正文首个 `# ` 行(`services/document_writer._title_from_content` /
`knowledge-indexing` 的「文档标题提取」),所以「头部 h1」与「正文首个 H1」在绝大多数文档里
是同一串文本——这是重复的根因,而不是两处各自写错了。

## 决策

### D1 路径的唯一载体是面包屑,不是 Topbar

Topbar 显示的是「知识库 / 文件名」(`Layout.tsx` 的 `currentDocPath.split('/').pop()`),
粒度是**文件名**;面包屑逐段可点击,能跳到任意父级目录,粒度是**完整路径**。
两者粒度不同,保留;被删掉的是 meta 行里**与面包屑完全同粒度**的那份路径。

不选「删掉面包屑、只留 Topbar」:面包屑的逐段跳转是树的替代导航,删掉会丢能力。

### D2 meta 行用「来源」替换路径

meta 行原位置改为文档来源:

| `document.node_id` | 显示 |
| --- | --- |
| `local` | 本机(Hub 自身扫描的知识库目录) |
| 其他 | 该节点的 `name`(取不到时回退 `node_id`) |

理由:路径已有载体(面包屑),继续重复是纯噪声;而「来源」是当前缺失、且读者真正需要的信息
(多机场景下「这篇是谁同步上来的」)。节点名通过 `api.getNodes()` 解析,仅在**非本机文档**
时发起该请求,取不到就回退 `node_id`——不新增接口、不改响应字段。

> 注:该字段也是后续「按来源决定是否可编辑」的落点,但**本次变更不做编辑门控**
> (编辑语义涉及服务端来源标记,见「不在本次范围」)。

### D3 标题去重放在渲染层,不放入库层

`document.title` 是**索引字段**:文档列表、文件树、搜索结果、MCP 输出都在用。
若在入库时把正文的 `# ` 行删掉,会连带改变 hash、向量分块上下文与 `get_document` 的输出,
影响面远超阅读体验。因此去重只发生在 `MarkdownViewer` 的渲染前一步,数据零改动。

剥离条件刻意收窄,避免误伤:

1. 只检查**首个非空行**(前导空行跳过);
2. 该行必须是 ATX 一级标题 `# xxx`;
3. `xxx.trim()` 必须与 `document.title.trim()` **完全相等**;
4. 只剥离这一行。正文中间、以及 `## ` 及更深的标题一律不动。

不满足任一条件即原样渲染(例如标题来自文件名、或正文刻意以别的 H1 开篇)。

### D4 过滤下拉缩短文案,而不是放宽宽度

`.tree-toolbar__row .select` 与三个图标按钮同排、`flex: 1; min-width: 0`,树面板宽度可拖拽且
可以很窄。放宽 `min-width` 会把图标按钮挤出面板;而原生 `<select>` 的选中项文本无法用
`text-overflow` 加省略号。文案从「全部 RAG 状态」缩到「全部状态」是满足可读性的最小改动,
语义不丢(该下拉的选项本身就是 RAG 状态)。

## 不在本次范围(已识别,另行决策)

**文档编辑的持久性**。当前 Hub 端的编辑对「有对应磁盘文件」的文档是**暂态**的:

- 节点来源文档:节点下一轮同步(文件监听触发或默认 300 秒对账)会用本地文件覆盖 Hub 内容
  (机制:Hub 重算 hash → 节点报 hash-only → Hub 判 `hash mismatch` 拒绝 → 节点把该路径移出快照
  → 下轮带全文重传);
- `local` 文档:Hub 执行扫描(`POST /api/documents/scan`)时,`indexer.sync_documents` 以
  「local 表里有、本次扫描没扫到 → 删」推导,会把**不在磁盘上**的文档删掉——包括
  `POST /api/documents` / MCP `create_document` 新建的文档。

要正确处理,需要给文档加**来源标记**(区分「来自文件扫描」与「Hub/智能体写入」),涉及模型、
迁移、扫描/同步删除推导、写入口径与前端编辑门控。这是一次独立变更,不与本次呈现层改动混做。
