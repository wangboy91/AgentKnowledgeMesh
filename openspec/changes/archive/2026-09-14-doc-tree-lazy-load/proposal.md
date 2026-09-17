# Proposal: doc-tree-lazy-load

## Why

文档树端点当前一次性返回整棵树、前端每次切换节点整树重拉:实测 1 万篇文档无压缩 payload 约 1MB、5 万篇约 5.4MB,且 FileTree 还并行再拉一份全量文档列表(仅为了 path→id 解析)。规模上去后切换节点白屏、传输与内存都不可持续。

## What Changes

- `GET /api/documents/tree` 新增可选 `dir` 查询参数:**缺省(不传)返回完整树,行为与现状一致(向后兼容);传值(含空串=根)返回该目录的一层直接子项**(目录占位 `{}`,文件节点携带 `_title/_path/_rag_status/id`)
- 树叶子节点(全量与切片模式)统一新增 `id` 字段,前端 RAG 勾选不再依赖全量文档列表
- `GET /api/documents` 新增可选 `path` 精确匹配参数(组合 `node_id` 唯一定位),Knowledge 页按 path 解析 doc id 时不再全量拉取
- 前端 FileTree 重构为折叠懒加载:目录内容平铺缓存(childrenByDir),展开某目录才请求其一层子项;RAG 单/批量操作改为从叶子节点携带的 id 直取
- 「全部展开」保留:一次全量请求后本地拆平缓存(用户显式触发)
- server 增加 `GZipMiddleware`(minimum_size=1024);SSE(`text/event-stream`)由 starlette 跳过压缩,不受影响

## Capabilities

### Modified Capabilities

- `document-management`: 树端点支持目录切片与叶子 id;文档列表支持 path 精确匹配
- `knowledge-browsing`: 文档树改为按目录懒加载交互(展开才拉取一层)

## Impact

- **server**:`documents.py` 树/列表两个端点参数扩展(缺省行为不变);`main.py` 加 GZip 中间件
- **web**:`FileTree.tsx` 懒加载重构(树数据流核心变化,交互与文案不变);`client.ts` 两个函数加参数;`Knowledge.tsx` path 解析改精确查询
- **兼容**:tree/list 不带新参数行为不变;`filter` 语义从"全树过滤"变为"已加载且已展开范围过滤"(等价旧行为 = filter + 全部展开)
- **性能**:切换节点首屏只拉顶层一层;展开目录只拉该目录一层;传输量从 O(全量文档) 降为 O(可见目录)
