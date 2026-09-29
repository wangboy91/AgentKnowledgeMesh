# subpath-deployment Specification

## Purpose
系统可部署在反向代理的任意深度 URL 子路径下(`https://xx.com/akm`、`https://xx.com/tools/kb`),前缀由单一配置项决定;同一份前端构建产物无需为不同前缀重新构建。

## Requirements

### Requirement: Configurable Root Path
系统 SHALL 提供单一配置项 `AKM_ROOT_PATH` 声明外部访问前缀;取值 SHALL 支持任意深度(如 `/akm`、`/tools/kb`);缺省为空表示部署在域名根路径,**此时全部行为与不配置时一致**。

#### Scenario: 根路径部署(缺省)
- **WHEN** 未设置 `AKM_ROOT_PATH`
- **THEN** 服务在域名根路径下提供全部端点,行为与未引入本能力时完全一致

#### Scenario: 单层前缀
- **WHEN** 设置 `AKM_ROOT_PATH=/akm`
- **THEN** Web 界面与 API 均在该前缀下可用(`https://xx.com/akm/...`)

#### Scenario: 多层前缀
- **WHEN** 设置 `AKM_ROOT_PATH=/a/b/c`
- **THEN** Web 界面与 API 均在该前缀下可用,层级数不受限制

#### Scenario: 输入容错
- **WHEN** `AKM_ROOT_PATH` 写成 `akm`、`/akm/` 或 `/`
- **THEN** 系统归一化为 `/akm` 或空,并按归一化后的前缀工作

### Requirement: Sub-Path Aware SPA Serving
系统 SHALL 在服务 `index.html` 时注入当前前缀作为文档基址与运行时基址,使前端资源引用与路由在该前缀下正确解析;**同一份构建产物 SHALL 无需重新构建即可在任意深度前缀下运行**。静态目录中的其它文件 SHALL 原样返回,不做注入。

#### Scenario: 注入基址
- **WHEN** 浏览器请求该前缀下的任意非 API 路径(含 SPA 深链,如 `/akm/knowledge`)
- **THEN** 返回的 `index.html` 中已注入指向该前缀的文档基址与运行时基址

#### Scenario: 根路径部署时等价
- **WHEN** 未设置前缀时请求 SPA 路径
- **THEN** 注入的基址为 `/`,与未引入本能力时的解析结果一致

#### Scenario: 静态文件不注入
- **WHEN** 请求的是静态目录中真实存在的文件(如前端 JS/CSS 资源)
- **THEN** 原样返回该文件,内容不被改写

### Requirement: Sub-Path Aware Client Runtime
Web 前端 SHALL 依据运行时注入的基址确定路由 basename 与 API 基址,不得写死根路径;注入缺失或非法时 SHALL 回退为根路径。

#### Scenario: 子路径下路由与 API
- **WHEN** 前端在前缀 `/akm` 下运行
- **THEN** 路由 basename 为 `/akm`(深链可直接打开),API 请求发往前缀下的 `/akm/api/...`

#### Scenario: 注入缺失时回退
- **WHEN** 前端在开发服务器或根路径部署下运行(无注入)
- **THEN** 路由 basename 为 `/`、API 基址为 `/api`,与现状一致

### Requirement: Reverse Proxy Compatibility
系统 SHALL 同时支持反向代理**剥离**前缀(如 nginx `proxy_pass http://hub:8000/`)与**保留**前缀(如 `proxy_pass http://hub:8000`)两种配置写法,客户按既有网关习惯配置即可。

#### Scenario: 代理剥离前缀
- **WHEN** 代理把 `/akm/api/health` 转发为应用路径 `/api/health`
- **THEN** 请求正常命中路由并返回 200

#### Scenario: 代理保留前缀
- **WHEN** 代理把 `/akm/api/health` 原样转发(应用收到带前缀的路径)
- **THEN** 请求正常命中路由并返回 200

#### Scenario: 静态资源在两种代理写法下均可访问
- **WHEN** 配置了前缀后请求前端静态资源(`/assets/*`、站点图标等)
- **THEN** 无论代理剥离还是保留前缀,系统均返回该文件(200),不得因前缀被重复拼接而 404

#### Scenario: 对外通告地址带前缀
- **WHEN** 配置了前缀后访问 OpenAPI 文档或建立 MCP SSE 连接
- **THEN** 系统对外通告的地址(OpenAPI `servers`、SSE 消息端点)均带该前缀,客户端可据此直接回发
