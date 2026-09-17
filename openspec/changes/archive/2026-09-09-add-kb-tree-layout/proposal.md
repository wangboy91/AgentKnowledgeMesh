# Proposal: add-kb-tree-layout

## Why

知识库页当前无法按节点维度浏览:所有节点的文档混在一起扁平展示,缺少目录树导航;用户期望"选节点 → 浏览树 → 点开渲染"的三栏式知识浏览体验。

## What Changes

- 知识库页改为三栏布局:节点列表(左,现有 NodeList 收窄复用)→ 文档树(中)→ 文档渲染(右,MarkdownViewer)
- 中栏文档树**默认全部收起**,目录可逐级展开/收起,提供"全部展开/收起"快捷操作;展开状态按节点记忆(`localStorage` 键 `akm.tree.<node_id>`)
- 点选树中文档 → 右栏渲染;未选中文档时右栏显示占位引导
- 顶栏全局搜索命中后联动:跳转知识库页、定位并展开文档所在路径、右栏渲染
- `GET /api/documents/tree` 支持 `?node_id=` 按节点过滤(不带参数返回全部,向后兼容)
- 窄屏(<1024px)退化为两栏(树与文档切换显示)

## Capabilities

### New Capabilities

- `knowledge-browsing`: 知识库页的三栏浏览交互(节点选择、树形导航、文档渲染联动)

### Modified Capabilities

- `document-management`: 文档树端点支持按节点过滤

## Impact

- **server**:`/api/documents/tree` 增加 `node_id` 查询参数(默认行为不变)
- **web**:`Knowledge.tsx` 三栏重构;`FileTree.tsx` 增强为受控展开态组件;`NodeList.tsx` 收窄复用;搜索联动逻辑
- **兼容**:tree 端点不带参数行为不变;其余页面不受影响
