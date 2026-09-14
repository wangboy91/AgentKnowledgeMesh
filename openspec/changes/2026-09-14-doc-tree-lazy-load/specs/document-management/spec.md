# document-management 能力增量(树目录切片与叶子 id)

## MODIFIED Requirements

### Requirement: Document Tree
系统 SHALL 提供 `GET /api/documents/tree` 端点,将文档路径组织为文件树;SHALL 支持可选 `node_id`(按节点过滤)与可选 `dir`(目录切片)查询参数;文件节点 SHALL 携带 `id`。

**缺省(不传 `dir`)时返回完整嵌套树(向后兼容);传 `dir`(含空串=根)时 SHALL 仅返回该目录的一层直接子项:文件节点为 `{_title, _path, _rag_status, id}`,子目录为 `{}` 占位。**

#### Scenario: 目录切片一层性
- **WHEN** 索引存在 `docs/a.md` 与 `docs/sub/b.md`,客户端调用 `GET /api/documents/tree?dir=docs`
- **THEN** 返回 `{"a.md": {...含 id...}, "sub": {}}`,不包含 `b.md`(仅一层)

#### Scenario: 根切片
- **WHEN** 客户端调用 `GET /api/documents/tree?dir=`(空串)
- **THEN** 返回顶层一层子项(顶层目录为 `{}` 占位,顶层文件带完整元信息)

#### Scenario: 不存在的目录
- **WHEN** 客户端调用 `GET /api/documents/tree?dir=ghost`
- **THEN** 返回 `{}`

#### Scenario: 特殊字符目录名
- **WHEN** 目录名含 `%` 或 `_` 等 LIKE 通配字符
- **THEN** 切片仍精确匹配该目录,不误匹配其他目录

#### Scenario: 缺省参数兼容
- **WHEN** 客户端调用 `GET /api/documents/tree`(不带 dir)
- **THEN** 返回完整嵌套树,与既有行为一致(叶子多 `id` 字段)

## ADDED Requirements

### Requirement: Document Path Lookup
`GET /api/documents` SHALL 支持可选 `path` 查询参数,提供时仅返回该精确路径的文档(等值匹配,非模糊);可与 `node_id` / `rag_status` 组合。

#### Scenario: 按 path 精确定位
- **WHEN** 客户端调用 `GET /api/documents?node_id=<节点>&path=docs/a.md`
- **THEN** 返回该 (节点, 路径) 下的单条文档(含 `id`);未命中返回 `[]`
