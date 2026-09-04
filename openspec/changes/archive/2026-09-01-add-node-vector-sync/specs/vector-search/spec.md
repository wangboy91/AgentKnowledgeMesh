## MODIFIED Requirements

### Requirement: Vector Index Management
系统 SHALL 提供 `POST /api/rag/index` 端点，将数据库中全部含内容的文档向量化入库；文档增删改时 SHALL 尽力同步向量索引，触发路径包括文档 API 的创建/更新/删除与节点文档推送的增量入库。

#### Scenario: 全量索引
- **WHEN** 客户端调用 `POST /api/rag/index`
- **THEN** 系统遍历全部文档，对每篇有内容的文档分块、嵌入并写入向量表，返回 `{"message", "indexed": N, "total_chunks": M}`

#### Scenario: 重复索引覆盖旧向量
- **WHEN** 对已索引文档再次入库
- **THEN** 系统先删除该文档的旧分块向量再写入新向量

#### Scenario: 文档生命周期同步
- **WHEN** 文档经索引同步、文档 API 创建/更新/删除，或节点文档推送被增量入库
- **THEN** 系统尽力同步向量索引（新增/覆盖/删除对应向量）；向量操作失败仅记录告警，不影响主流程

#### Scenario: 索引失败降级
- **WHEN** 全量索引过程发生异常
- **THEN** 系统返回 `{"message": "Index failed: ...", "indexed": 0}`，不抛出 500

## ADDED Requirements

### Requirement: Vector Backfill
系统 SHALL 提供存量回填脚本，为已入库但向量表中缺失向量的文档补建向量；已存在向量的文档 SHALL NOT 被重复嵌入。

#### Scenario: 只补缺失向量
- **WHEN** 回填脚本执行时，数据库中存在向量表中没有对应分块的文档
- **THEN** 系统仅对这些文档分块、嵌入并写入向量表，跳过向量表中已存在的文档

#### Scenario: 回填输出统计
- **WHEN** 回填脚本执行完成
- **THEN** 脚本输出补建向量与跳过的文档数量统计

#### Scenario: 回填失败降级
- **WHEN** 单篇文档嵌入失败
- **THEN** 脚本记录告警并继续处理其余文档，最终统计中如实反映失败数量
