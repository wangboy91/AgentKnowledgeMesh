# doc-viewer-header

## Why

知识库文档视图的头部把同一信息重复渲染,实测(2026-09-30 用户截图,浏览 `openspec/specs/document-conversion/spec.md`)表现为:

- **路径出现两遍**:`MarkdownViewer` 的面包屑逐段渲染完整路径,紧随其后的 meta 行又用 `document.path` 原样渲染一遍;且该行带 `maxWidth: 280` 截断,长路径被压成 `AgentKnowledge… /openspec /specs /document…`(省略号切在段中间,比不显示更难读)。而 Topbar 已经显示「知识库 / spec.md」。
- **标题出现两遍**:`document.title` 由正文首个 `# ` 行提取(`knowledge-indexing`「文档标题提取」),头部据此渲染 `<h1>`;而正文 Markdown 仍保留该 `# ` 行,被渲染成第二个一级标题。打开文档先看到两遍同样的标题。
- 文件树工具栏的 RAG 状态过滤下拉在窄面板下把「全部 RAG 状态」截成「全部 RAG 状」:`.tree-toolbar__row .select { flex: 1; min-width: 0 }` 允许原生 `<select>` 收缩,而原生 select 不会省略号提示。

头部噪声盖过正文,是当前阅读体验最直接的退化。

## What Changes

- **面包屑成为路径的唯一载体**;meta 行不再重复 `document.path`,改为显示**文档来源**(本机 / 来源节点名)。这同时补齐了一个信息位:读者能一眼看出这篇文档是从哪台机器同步来的。
- **正文渲染前剥离与标题重复的首个一级标题行**:仅当首个非空行是 ATX 一级标题(`# `)且其文本与 `document.title` 完全一致时剥离;正文中间的 H1 一律保留(可能是刻意分节)。
- **文件树 RAG 状态过滤的默认项文案缩短**:「全部 RAG 状态」→「全部状态」(`All RAG status` → `All statuses`),使窄面板下完整可读。

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `knowledge-browsing`:新增 Requirement「文档视图头部信息不重复」——路径由面包屑唯一承载、标题只渲染一次、meta 行标识文档来源

## Impact

- `src/web/src/components/MarkdownViewer.tsx`:meta 行去掉路径项、新增来源项;正文按标题去重
- `src/web/src/utils/markdown.ts`(新增):`stripLeadingTitle(content, title)` 纯函数
- `src/web/src/pages/Knowledge.tsx`:非本机文档时拉取节点列表以解析来源节点名
- `src/web/src/i18n/{zh,en}.ts`:新增来源/本机文案;`filetree.allStatus` 文案缩短
- `src/web/tests/`:新增 `stripLeadingTitle` 单测
- **无对外契约变更**(REST / WS / MCP 协议与响应字段均不变),Hub 端与节点端零改动,不影响已部署实例
- 与在制变更 `2026-09-30-add-node-env-login`(仅 `src/node/**`)无文件重叠
