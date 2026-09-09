# document-management 能力增量(树按节点过滤)

## MODIFIED Requirements

### Requirement: Document Tree
系统 SHALL 提供 `GET /api/documents/tree` 端点,将文档路径组织为嵌套的文件树结构;**SHALL 支持可选 `node_id` 查询参数:提供时仅包含该节点的文档,缺省时包含全部文档(行为与现状一致)。**

#### Scenario: 按路径层级构建树
- **WHEN** 索引中存在文档 `projects/ai-crm.md`(标题 "AI CRM System Design")
- **THEN** 返回结构为 `{"projects": {"ai-crm.md": {"_title": "AI CRM System Design", "_path": "projects/ai-crm.md"}}}`,目录层级逐层嵌套

#### Scenario: 按节点过滤
- **WHEN** 客户端调用 `GET /api/documents/tree?node_id=<某节点>`
- **THEN** 树仅包含该节点名下的文档,其他节点(含 `local`)文档不出现

#### Scenario: 缺省参数兼容
- **WHEN** 客户端调用 `GET /api/documents/tree`(不带 node_id)
- **THEN** 返回全部节点文档构成的树,与现有行为一致
