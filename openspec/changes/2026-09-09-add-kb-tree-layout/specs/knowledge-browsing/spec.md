# knowledge-browsing 能力规格(三栏浏览)

## Purpose

知识库页提供"节点 → 目录树 → 文档渲染"的三栏浏览体验,支持按节点导航目录、默认收起可展开、点选即渲染。

## ADDED Requirements

### Requirement: Three-Pane Knowledge Layout
知识库页 SHALL 呈现三栏布局:左栏为节点选择列表,中栏为所选节点的文档树,右栏为选中文档的 Markdown 渲染;未选中文档时右栏 SHALL 显示占位引导;视口宽度小于 1024px 时 SHALL 退化为两栏(树与渲染切换)。

#### Scenario: 选择节点加载树
- **WHEN** 用户在左栏选择某节点
- **THEN** 中栏加载并展示该节点的文档树(仅含该节点文档)

#### Scenario: 点选文档渲染
- **WHEN** 用户在中栏点选一个文档
- **THEN** 右栏渲染该文档的 Markdown 内容(GitHub 风格)

### Requirement: Collapsible Tree Navigation
文档树 SHALL 默认全部收起;目录 SHALL 可逐级展开与收起,并提供"全部展开 / 全部收起"快捷操作;每个节点的展开状态 SHALL 按节点持久化(下次进入同一节点时恢复)。

#### Scenario: 默认收起
- **WHEN** 用户切换到一个节点(该节点无已记忆的展开状态)
- **THEN** 树仅显示根层级的目录与文件,目录内容收起

#### Scenario: 展开状态记忆
- **WHEN** 用户展开某目录后离开该节点,稍后重新选择该节点
- **THEN** 之前展开的目录保持展开

#### Scenario: 批量展开收起
- **WHEN** 用户点击"全部展开"或"全部收起"
- **THEN** 树的所有目录层级对应展开或收起,并更新该节点的记忆状态

### Requirement: Search-to-Tree Linkage
顶栏全局搜索命中并选择某文档时,SHALL 跳转至知识库页、定位该文档、展开其所在路径并渲染到右栏。

#### Scenario: 搜索命中联动
- **WHEN** 用户在顶栏搜索并点选某命中文档
- **THEN** 界面切换到知识库页,该文档所在目录路径自动展开,右栏渲染该文档
