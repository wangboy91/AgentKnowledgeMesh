# Tasks: add-kb-tree-layout

## 1. 端点

- [x] 1.1 `GET /api/documents/tree` 增加 `node_id` 查询参数(过滤 `Document.node_id`),缺省行为不变;pytest 用例:按节点过滤、缺省兼容、不存在节点返回空树;`uv run pytest` 全绿
- [x] 1.2 `client.ts` 增加 `getDocumentTree(nodeId?)`;curl 验证两种调用

## 2. 三栏布局与树交互

- [x] 2.1 `Knowledge.tsx` 重构三栏(左 NodeList 收窄 / 中树 / 右渲染 + 空态占位);窄屏(<1024px)两栏退化;`npm run build` 通过
- [x] 2.2 `FileTree.tsx` 改受控组件(expanded 集合 + onToggle 回调);默认收起;逐级展开/收起;全部展开/收起快捷按钮
- [x] 2.3 展开状态按节点持久化(`localStorage` 键 `akm.tree.<node_id>`,ui.md 登记);切节点恢复;单节点 KB 级体积
- [x] 2.4 节点切换防御:右栏文档不属于新节点时清空回占位

## 3. 搜索联动

- [x] 3.1 SearchBar 选中命中 → 跳知识库页 → 按 path 逐段展开 → 右栏渲染;手测深层路径(≥3 级)与跨节点命中

## 4. 验证与收尾

- [x] 4.1 双主题 + 明暗走查;键盘可达性(目录可 Tab 聚焦回车展开);`uv run pytest` + `npm run build` 全绿
- [x] 4.2 README 使用说明更新(知识库页三栏);openspec verify
