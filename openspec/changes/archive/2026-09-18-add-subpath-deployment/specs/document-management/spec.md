# document-management 能力增量(SPA 托管支持部署前缀)

## MODIFIED Requirements

### Requirement: Production SPA Serving
系统 SHALL 在生产模式下（存在前端构建产物时）托管静态资源，并对非 API 路径提供 SPA 路由回退；返回的 `index.html` SHALL 携带当前部署前缀作为文档基址与运行时基址（见 `subpath-deployment` 能力），使同一份构建产物可在任意深度子路径下运行。

#### Scenario: 前端路由回退
- **WHEN** 请求的非 API 路径在静态目录中没有对应文件
- **THEN** 系统返回 `index.html`，由前端路由接管

#### Scenario: 回退页面携带部署基址
- **WHEN** 部署配置了子路径前缀后请求任一非 API 路径（含 SPA 深链）
- **THEN** 返回的 `index.html` 已注入指向该前缀的文档基址与运行时基址

#### Scenario: 静态资源原样返回
- **WHEN** 请求的是静态目录中真实存在的资源文件
- **THEN** 该文件原样返回，不注入任何内容

#### Scenario: 静态解析限定在静态目录内
- **WHEN** 请求路径包含 `..` 等试图逃出静态目录的片段
- **THEN** 系统不返回静态目录之外的文件（回退为 `index.html` 或 404），不得泄露源码等目录外内容
