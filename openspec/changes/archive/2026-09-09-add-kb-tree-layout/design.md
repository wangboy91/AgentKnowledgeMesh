# Design: add-kb-tree-layout

## Context

现状:Knowledge 页为"搜索 + 扁平文档列表 + 渲染"两区结构;`/api/documents/tree` 返回全部节点混合的树;`FileTree.tsx` 为自渲染折叠树;`NodeList.tsx` 供节点选择。方案详见 [docs/technical-design.md](../../../docs/technical-design.md) §7。

## Goals / Non-Goals

**Goals:**
- 三栏体验:节点维度导航、树形目录、点选即渲染
- 树状态按节点记忆,切换节点体验连续
- 搜索 → 树定位联动,形成"搜到即看到"闭环

**Non-Goals:**
- 树内联编辑、拖拽、多选(仍走文档列表/编辑器路径)
- 虚拟滚动(知识库量级未到;树组件保持简单)
- 双栏宽度自由拖拽(沿用现有 ResizeHandle 仅用于侧栏)

## Decisions

1. **tree 端点加 `node_id` 参数而非新端点**:能力内聚在 document-management,前端一次请求得单节点树;缺省行为不变,兼容现有调用。
2. **FileTree 改受控组件**:`expanded: Set<path>` 由父组件持有并按节点持久化(`akm.tree.<node_id>`),FileTree 只负责渲染与回调 —— 搜索联动、全部展开/收起都在父层操作同一状态,避免组件内外双状态源。
3. **节点切换保留已加载文档渲染**:右栏文档未变时不重置;仅当文档不属于新节点时清空回占位(防御跨节点残留)。
4. **窄屏退化用 CSS 断点 + 状态切换**(<1024px 树/渲染二选一显示,以"当前选中"优先),不引入响应式框架。
5. **搜索联动复用现有 SearchBar 下流选择事件**:携带 doc 路径跳转知识库页,按 path 逐段展开目标(树结构即路径层级,可直接推导)。

## Risks / Trade-offs

- [大树渲染卡顿] → 当前量级(<数千节点)无压力;出现性能问题时再上虚拟化(Non-Goal 已声明)
- [展开状态存储膨胀] → 仅存展开目录 path 集合,单节点 KB 级;localStorage 键登记进 ui.md
- [与 add-rag-sync-modes 同页改动] → 该变更加状态徽标于文档列表(非本页树);冲突面小,apply 时注意 rebase 顺序

## Migration Plan

纯前端重构 + 一个只增参数的端点变更;无数据迁移。回滚即代码回退。

## Open Questions

无。
