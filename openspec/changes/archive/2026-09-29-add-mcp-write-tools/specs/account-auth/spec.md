# account-auth 能力增量(节点凭证受限写权限)

## MODIFIED Requirements

### Requirement: 端点鉴权矩阵
除 `GET /api/health` 与登录端点外,全部 `/api` 端点 SHALL 要求有效 Bearer 凭证(JWT、API Token 或节点 token 三选一);**读操作(GET)**对 admin、viewer 及节点 token 放行;**写操作**(POST/PUT/DELETE)SHALL 仅限 admin,**但文档写端点**(`POST /api/documents` 创建、`PUT /api/documents/{doc_id}` 更新)对节点凭证放行且**作用域限该节点名下文档**——节点凭证创建的文档归属该节点,仅能更新 `node_id` 等于该节点的文档;用户管理与 API Token 管理 SHALL 仅限 admin。凭证无效或缺失 SHALL 返回 401,角色不足 SHALL 返回 403,跨作用域写入 SHALL 返回 403。

#### Scenario: 未认证访问被拒
- **WHEN** 不携带凭证调用 `GET /api/documents`
- **THEN** 返回 401

#### Scenario: viewer 只读
- **WHEN** viewer 调用 `POST /api/documents/scan`
- **THEN** 返回 403;同一用户调用 `GET /api/search` 正常返回

#### Scenario: 节点凭证只读
- **WHEN** 以节点 token 调用 `GET /api/search`
- **THEN** 正常返回;同一 token 调用 `POST /api/documents/scan` 或 `DELETE /api/nodes/{id}` 返回 403

#### Scenario: 节点凭证可写本节点文档
- **WHEN** 以节点 token 调用 `POST /api/documents` 或 `PUT /api/documents/{doc_id}`(目标文档归属该节点)
- **THEN** 放行;创建时 `node_id` 强制为该节点

#### Scenario: 节点凭证跨作用域写入被拒
- **WHEN** 以节点 token 更新归属其他节点或 `local` 的文档
- **THEN** 返回 403

#### Scenario: 鉴权豁免清单
- **WHEN** 未携带凭证调用 `GET /api/health` 或 `POST /api/auth/login`
- **THEN** 正常响应
