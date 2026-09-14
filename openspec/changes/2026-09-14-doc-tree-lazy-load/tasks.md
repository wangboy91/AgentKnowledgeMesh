# Tasks: doc-tree-lazy-load

## 1. 后端契约

- [x] 1.1 `GET /api/documents/tree` 新增 `dir` 参数(缺省全量向后兼容;传值含空串返回一层切片),SELECT 增加 `Document.id`,叶子节点统一携带 `id`;SQL 用 `path.startswith(prefix, autoescape=True)` + Python 二次精筛;pytest 用例:根切片一层、子目录切片一层(含 id)、切片+node 过滤、不存在目录、尾斜杠归一、特殊字符(`%`/`_`)、全量叶子带 id
- [x] 1.2 `GET /api/documents` 新增 `path` 精确匹配参数(组合 node_id/rag_status);pytest 用例:精确命中单条、未命中空列表、组合 rag_status
- [x] 1.3 `main.py` 增加 `GZipMiddleware(minimum_size=1024)`;确认 SSE 不受影响(starlette 对 text/event-stream 跳过)
- [x] 1.4 `uv run pytest` 全绿(含存量 7 个树用例零改动)

## 2. 前端懒加载

- [x] 2.1 `client.ts`:`getDocuments` 加 `path` 参数;`getDocumentTree` 加 `dir` 参数(URLSearchParams 构造,`dir !== undefined` 才传;修掉模板串不编码隐患)
- [x] 2.2 `FileTree.tsx` 重构:删除 `tree`/`docs` 全量状态与双请求,改为 `cacheRef/inflightRef/epochRef/nodeRef` 平铺缓存;`loadDir` 幂等(缓存/在途复用、节点与代际守卫);切节点重置+根切片;惰性拉取 effect 驱动展开加载;`reloadDirs` 作废重载;渲染从 `childrenByDir` 取子项(展开未加载 → loading 行;根未加载 → 面板 loading;根空 → 扫描空态)
- [x] 2.3 RAG 交互:`toggleRag` 改收叶子节点(直接用 `id`/`_rag_status`),成功后 reload 父目录;`picked` 改 `Map<path, id>`,`confirmBatch` 直接取 id 并 reload 相关父目录
- [x] 2.4 「全部展开」:一次全量请求 + `decompose` 拆平缓存;「全部收起」不变;刷新/扫描后 reload 已加载目录
- [x] 2.5 `Knowledge.tsx`:`loadDocument` 改 `getDocuments(nodeId, undefined, normalized)` 取首条,删全量 find
- [x] 2.6 `npm run build`(tsc 净面)+ `npm run test` 通过

## 3. 文档与收尾

- [x] 3.1 `docs/api-reference.md` 同步两个端点的新参数说明
- [ ] 3.2 手工验证清单走查(展开/连点防重/RAG 局部重载/搜索与深链逐层展开/全部展开/切节点恢复)
- [x] 3.3 上万文档规模验证(`scripts/seed_big_tree.py` 注入独立 sqlite 2 万篇:全量 2.25MB/0.35s、GZip 238KB(9.4x,`content-encoding: gzip` 确认)、根切片 37B、单目录切片 ~2KB/30ms、特殊字符 `%`/`_` 精确切片无跨目录泄漏、`?path=` 精确命中)
- [ ] 3.4 openspec verify 后归档
