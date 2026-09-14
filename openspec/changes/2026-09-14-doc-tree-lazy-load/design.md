# Design: doc-tree-lazy-load

## 1. 树端点目录切片(`dir` 参数)

`GET /api/documents/tree?node_id=X&dir=<目录路径>`:

- **缺省 `dir`(不传)**:完整树,与现状一致(向后兼容,存量测试零改动)
- **`dir=""`(根切片)**:返回顶层一层子项
- **`dir="docs"`**:返回 `docs` 的一层直接子项

返回结构(一层 dict):

- 文件节点:`{"_title": ..., "_path": 完整路径, "_rag_status": ..., "id": doc_id}`
- 目录节点:`{}` 占位(不加载其内容;真实空目录与未加载目录由前端缓存判别)

实现要点:

- SQL 过滤:`Document.path.startswith(dir.rstrip("/") + "/", autoescape=True)` —— SQLAlchemy 实测渲染为 `LIKE ? || '%' ESCAPE '/'`,`%`/`_`/`/` 均正确转义;命中 `(node_id, path)` 复合唯一索引
- Python 侧二次精筛 `path.startswith(prefix)`(防部分方言 LIKE 大小写宽松导致超集)
- 构建:`rest.partition("/")`;有 tail → 目录占位 `setdefault(seg, {})`(同名文件/目录并存时文件分支优先,FS 不可达仅防御)
- 尾斜杠归一:`dir.rstrip("/")`

## 2. 叶子携带 id

全量与切片模式的文件节点统一加 `id`(int)。前端 RAG 单篇/批量勾选直接用树叶子 id,FileTree 不再需要全量 `getDocuments`。

## 3. 文档列表 path 精确匹配

`GET /api/documents?node_id=X&path=<完整路径>`:`WHERE node_id = ? AND path = ?`(等值,非模糊)。供 Knowledge 页"URL path → doc id"解析(原实现全量拉取后 find)。

## 4. 前端懒加载状态模型(FileTree.tsx)

```
cacheRef   Record<dir, 一层dict>     平铺目录缓存('' = 根;key 存在即已加载,空目录也缓存)
inflightRef Record<dir, Promise>     并发防重:同目录并发展开只发一次
epochRef   Record<dir, number>       每目录代际:reload 时 +1,使在途旧响应失效
nodeRef    当前节点                  切节点后丢弃在途响应,防串库
expanded   string[]                  展开集合(localStorage 持久化,key 不变)
```

- `loadDir(dir)`:缓存命中/在途复用;完成后「节点未切换且代际未变」才写缓存
- 切节点 effect:清空三个 ref,`loadDir('')`(根切片;空根 → 扫描引导空态)
- 惰性拉取 effect(依赖 expanded):对展开集中每个目录 `loadDir`。统一覆盖三个场景:点目录展开、首屏恢复记忆的展开集、搜索跳转/URL 深链(既有 `ancestorDirs(activePath)` 补展开逻辑不动)
- `reloadDirs(dirs)`:删缓存+在途、代际+1、重载。用于 RAG 操作后重拉父目录、扫描/刷新后重载已加载目录
- `expandAll`:一次全量请求(`getDocumentTree` 不带 dir)+ `decompose` 递归拆平成 byDir 缓存 + 展开全部;成本回到全量,仅用户显式触发,有 busy 态

## 5. 交互语义变化(有意为之)

- **RAG 状态 filter**:作用于"已加载且已展开"范围(等价旧行为 = filter + 全部展开)
- **切走再切回节点**:目录内容不落盘,按记忆的展开集重新逐层拉取
- **点选文件不触发任何树请求**(原先也不重拉,保持)

## 6. GZip

`main.py`:`app.add_middleware(GZipMiddleware, minimum_size=1024)`。已核实安装版 starlette 对 `text/event-stream` 跳过压缩且不缓冲(MCP SSE 长连接安全);WS 不经 http 中间件。万级 JSON 树压缩比实测 ~11x。

## 7. 测试策略

- 后端 pytest:切片一层性(根/子目录)、切片 + node 过滤、叶子携带 id、不存在目录、特殊字符(`%`/`_`)、`documents?path=` 精确及组合过滤;存量 7 用例不动保持绿
- 前端:`npm run build`(tsc)+ `npm run test`;无组件单测(现状仅 i18n parity),懒加载行为靠手工验证清单
