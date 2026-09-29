# Proposal: subpath-deployment

## Why

客户/内网部署时常把整个服务挂在反向代理的**子路径**下(`https://xx.com/akm`、`https://xx.com/akm-hub`,甚至 `https://xx.com/tools/kb`)—— 前缀名称与层级在部署前不可知,由客户的网关规划决定。当前实现只支持**根路径部署**,子路径下不可用:

| 位置 | 现状 | 子路径下的表现 |
| --- | --- | --- |
| 前端 `index.html` 资源引用 | 绝对路径 `/assets/...`、`/vault.svg` | 浏览器请求 `xx.com/assets/...` → 404,白屏 |
| 前端 API 基址 | `const BASE_URL = '/api'` | 请求 `xx.com/api/...` → 404(前缀丢失) |
| 前端路由 | `<BrowserRouter>` 无 `basename` | 访问 `xx.com/akm/knowledge` 匹配不到路由 |
| 服务端 | 未设置 `root_path` | OpenAPI `servers`、`url_for`、MCP SSE 通告地址都缺前缀 |
| 节点 | `AKM_HUB_API_URL` / `AKM_HUB_URL` 显式全 URL | **已可用**(`_derive_ws_url` 会保留 `/akm` 段) |

关键在于:前端资源引用是**构建期写死的绝对路径**,代理层无法靠改写解决 —— 除非让客户把整个服务重新构建一遍,而构建期又不可能知道前缀。因此必须做成**运行时可配置**。

## What Changes

- 新增服务端配置 `AKM_ROOT_PATH`:外部访问前缀,支持任意深度(`/akm`、`/tools/kb`);空 = 根路径部署(**默认,行为与现状完全一致**)
- `FastAPI(root_path=...)`:经实证同时兼容两种反代写法 —— 代理**剥离**前缀(`proxy_pass http://hub:8000/`)与代理**保留**前缀(`proxy_pass http://hub:8000`),客户按自己的网关习惯配置即可
- `index.html` 在**服务时**注入 `<base href="{前缀}/">` 与 `window.__AKM_BASE__`;前端据此确定路由 basename 与 API 基址 → **同一份构建产物可在任意深度子路径下运行,无需重新构建**
- Vite 生产构建改用相对基路径(`base: './'`),开发服务器保持 `/` 不受影响
- 修正 MCP SSE 通告的消息端点(见下)

## 顺带修正: MCP SSE 通告地址错误(实证)

`SseServerTransport("/messages")` 通告的 endpoint 是 `/messages`,而实际路由是 `POST /api/mcp/messages`。本机实测(临时 Hub :8126):

```
SSE 通告:  data: /messages?session_id=...
POST /messages            -> 404
POST /api/mcp/messages    -> 202 Accepted
```

即**任何按 SSE 通告地址回发的 MCP 客户端都会 404**。改为通告完整路由路径 `/api/mcp/messages` 后,配合 `root_path` 自动得到 `{前缀}/api/mcp/messages`。这是子路径部署能跑通 MCP SSE 的前提,故并入本变更。

## Capabilities

### Added Capabilities

- `subpath-deployment`: 系统可在任意深度的 URL 子路径下部署运行,前缀由单一配置项决定,无需重新构建前端

### Modified Capabilities

- `document-management`: `Production SPA Serving` 增加"按根路径注入基址"的语义(同一份产物适配任意前缀)
- `mcp-integration`: `MCP Server Transports` 明确 SSE 通告的消息端点必须是实际可用的完整路由路径,并随根路径拼接

## Impact

- **server**:`config.py` 加 `AKM_ROOT_PATH` 与规范化;`main.py` 用 `root_path` 建 app 并实现 index.html 注入;`api/mcp.py` 修 SSE 端点常量
- **web**:`vite.config.ts` 构建基路径;新增 `runtime.ts`(基址解析);`main.tsx` 传 router basename;`api/client.ts` 用运行时 API 基址;`index.html` favicon 改 `%BASE_URL%`
- **deploy**:4 个 Hub compose 透传 `AKM_ROOT_PATH`;`.env.example` 增补
- **node**:无代码改动(显式 URL 已支持子路径),仅文档说明写法
- **兼容**:`AKM_ROOT_PATH` 默认空 → 根路径部署行为不变;存量测试不受影响
- **风险**:注入 `<base href>` 会改变文档内**所有**相对 URL 的解析基准 —— 已核对前端不使用相对 URL 形式的 fetch/资源引用(除本次改为 base 感知的 favicon),且子路径下 base 指向自身前缀,根路径下为 `/`,与现状等价
