# Design: subpath-deployment

## 1. 配置项与规范化

`AKM_ROOT_PATH`(server,字符串,默认空):

```
""            -> 根路径部署(默认,行为与现状完全一致)
"/akm"        -> https://xx.com/akm/...
"/akm-hub"    -> https://xx.com/akm-hub/...
"/tools/kb"   -> 任意深度,层级数不限
"akm/"        -> 容错:补前导斜杠、去尾部斜杠,归一为 "/akm"
"/"           -> 归一为 ""
```

规范化函数 `normalize_root_path(raw) -> str`(放 `config.py`,纯函数便于单测):

- `strip()` → 空则返回 `""`
- 去掉首尾空白与尾部所有 `/`
- 不以 `/` 开头则补上
- 结果为 `"/"` 或 `""` 时返回 `""`

`settings.root_path` 存**规范化后**的值,避免各处重复处理。

## 2. 服务端:为什么是 `FastAPI(root_path=...)` 而不是 uvicorn `--root-path`

`FastAPI.__call__` 在 `self.root_path` 非空时执行 `scope["root_path"] = self.root_path`(已核对 fastapi 源码);Starlette 的路由匹配走 `get_route_path(scope)`,后者在 `path` 以 `root_path` 开头时**剥掉**它、否则原样返回。

组合结果 —— **两种反代写法都能匹配**(以 `AKM_ROOT_PATH=/akm` 直接以 ASGI 调用实测):

| 客户代理写法 | 应用收到的 path | 匹配结果 |
| --- | --- | --- |
| 剥离前缀 `proxy_pass http://hub:8000/` | `/api/health` | 200 ✓(path 不以 /akm 开头 → 不剥离 → 命中) |
| 保留前缀 `proxy_pass http://hub:8000` | `/akm/api/health` | 200 ✓(剥掉 /akm → 命中) |

同时实测 `scope["root_path"]` 恒为 `/akm`、`openapi.json` 的 `servers` 为 `[{"url": "/akm"}]` —— 这正是 `url_for`、OpenAPI 文档、MCP SSE 通告地址所需的前缀来源。

选 `FastAPI(root_path=...)` 而非 `uvicorn --root-path` 的理由:

- uvicorn 的 `--root-path` 会把前缀**前置**到 `scope["path"]`,因而**只**支持"代理剥离前缀"一种写法;`FastAPI(root_path=...)` 两种都支持
- Dockerfile 的 `CMD ["uv", "run", "uvicorn", "app.main:app", ...]` 是 exec 形式,加 `--root-path` 得改成 shell 形式并做变量展开;用 `FastAPI(root_path=...)` 则 Dockerfile **零改动**
- `python -m app` 与 `uvicorn app.main:app` 两条启动路径行为一致

## 3. 前端基址:运行时注入,不重新构建

**约束**:构建期不知道前缀,且前缀层级不定 → 只能运行时决定。

**方案**:服务端在**服务 `index.html` 时**注入两行,前端读取:

```html
<head>
  <base href="/akm/" />
  <script>window.__AKM_BASE__ = "/akm/";</script>
  ...
```

分工:

- `<base href>` 解决**浏览器层**的相对 URL 解析 —— 构建产物里 `./assets/index-xxx.js`、`./vault.svg` 自动解析到 `/akm/...`,前端代码零感知
- `window.__AKM_BASE__` 给**应用层**一个显式基址 —— react-router 的 `basename` 与 API 基址

为什么两个都要:react-router 的 `basename` 不读 `document.baseURI`;而若只注入 `<base>`,应用就得从 `document.baseURI` 反推基址,在**开发服务器**下 `document.baseURI` 等于当前路由 URL(`/knowledge`),会把路由段误当基址。

**实现**:`create_app()` 时读一次 `static/index.html`,做一次字符串替换后缓存(HTML 小,不逐请求读盘):

- `<head>` → `<head>` + `<base href="{root}/" />` + `<script>window.__AKM_BASE__ = "{root}/";</script>`
- `root` 为空时 `<base href="/" />`、`window.__AKM_BASE__ = "/"`,与现状等价
- 只替换**首个** `<head>`,不改写其余内容(原相对引用原样保留,由 `<base>` 决定解析结果)

SPA catch-all 调整:

```
请求路径命中静态目录中的真实文件(且不是 index.html)→ FileResponse(原样,不注入)
否则                                                  → HTMLResponse(注入后的 index.html,带 no-cache)
```

`static/index.html` 文件本身保持原样,便于对照排查。

### 3.1 顺带修正:去掉 `/assets` 的 `StaticFiles` 挂载

原实现是 `app.mount("/assets", StaticFiles(directory=static/assets))`。**加了 `root_path` 之后它会坏掉**:

`Mount.matches` 会把挂载点追加进子 scope 的 `root_path`(`root_path + matched_path`),而 `StaticFiles` 内部又用 `get_route_path(scope)` 去剥 `root_path`。于是:

| 反代写法 | 应用收到的 path | 子 scope 的 root_path | StaticFiles 解析出的文件 | 结果 |
| --- | --- | --- | --- | --- |
| 剥离前缀 | `/assets/app.js` | `/akm/assets` | `static/assets/assets/app.js` | **404** |
| 保留前缀 | `/akm/assets/app.js` | `/akm/assets` | `static/assets/app.js` | 200 ✓ |

即"剥离前缀"这种更常见的写法下静态资源全挂。修法是**不再挂载**,静态文件统一走 catch-all 里的 `resolve_static_file()` 解析 —— 它直接用请求路径拼 `static/` 目录,两种写法结果一致(已单测 + 实测三种 `root_path` × 两种写法全 200)。

顺带把该解析函数加上了**目录穿越防护**(`resolve()` 后校验仍在 `static/` 内),原 catch-all 是裸 `static_dir / full_path`,存在 `../` 逃逸读取源码的风险。

## 4. 前端运行时基址模块(`src/web/src/runtime.ts`)

```ts
declare global {
  interface Window { __AKM_BASE__?: string }   // 服务端注入
}

export function normalizeBase(raw?: string | null): string   // 'akm' / '/akm' / '/akm/' -> '/akm/'
export const BASE_PATH: string = resolveBase()               // 恒以 '/' 结尾:'/' 或 '/akm/'
export function withBase(path: string): string               // withBase('/api') -> '/akm/api'
export const API_BASE: string = withBase('/api')             // '/api' 或 '/akm/api'
```

`resolveBase()` 的取值优先级:

1. `window.__AKM_BASE__` —— 服务端注入,**唯一权威来源**;
2. vite `import.meta.env.BASE_URL`(仅当其以 `/` 开头,即 dev 下的 `'/'`;生产构建是 `'./'`,不适用);
3. `'/'` —— 根路径兜底。

`basename` 直接用 `BASE_PATH`(带尾斜杠):react-router 的 `stripBasename` 明确保留尾斜杠语义,`navigate('/')` 会得到 `{basename}` 本身,`navigate('/knowledge')` 得到 `{basename}knowledge`,两种写法都对;因此**不需要**再派生一个去尾斜杠的常量。

`main.tsx`:`<BrowserRouter basename={BASE_PATH}>`;`client.ts`:`const BASE_URL = API_BASE`(fetch 的绝对路径不读 `<base>`,必须显式拼前缀)。

## 5. Vite 基路径

```ts
export default defineConfig(({ command }) => ({
  // 生产构建用相对基路径:产物中资源引用为 ./assets/*,由服务端注入的
  // <base href="{前缀}/"> 决定最终绝对位置 → 同一份 dist 适配任意深度的子路径,
  // 无需为每个客户重新构建。
  // 开发服务器仍用 '/' ,避免相对基路径在 dev 下的行为差异。
  base: command === 'build' ? './' : '/',
  ...
}))
```

`index.html` 的 favicon 从写死的 `/vault.svg` 改为 `%BASE_URL%vault.svg`(Vite 占位符,构建时替换为 `./`),并**补上缺失的 `public/vault.svg`**(该文件当前不存在,根路径部署下也是 404)。

## 6. MCP SSE 端点修正

```python
# 之前:SseServerTransport("/messages")
#   -> 通告 root_path + "/messages",而真实路由是 /api/mcp/messages,客户端回发 404
# 之后:SseServerTransport("/api/mcp/messages")
#   -> 通告 root_path + "/api/mcp/messages",根路径下为 /api/mcp/messages,
#      子路径下为 /akm/api/mcp/messages,均为真实可用地址
sse_transport = SseServerTransport("/api/mcp/messages")
```

该常量与 `@router.post("/messages")`(挂在 `include_router(mcp_router, prefix="/mcp")` + `include_router(router, prefix="/api")` 之下)必须保持一致 —— 加一条断言测试锁住二者关系,防止日后改路由忘改常量。

## 7. 部署侧

- `deploy/docker-compose.yml` / `.pg.yml` / `.external-pg.yml`(3 个 Hub compose):`environment` 增加 `- AKM_ROOT_PATH=${AKM_ROOT_PATH:-}`;`docker-compose.build.yml` 是只改镜像来源的叠加文件,自动继承
- `deploy/.env.example`:新增第 4 节「子路径部署」(含反代示例),原 4~7 节顺延为 5~8
- `deploy/docker-compose.node.yml`:注释补充子路径地址写法
- `docs/deployment.md`:新增 §1.9 子路径部署,给出 nginx / Caddy 两种反代写法、`AKM_ROOT_PATH` 与代理前缀必须一致、以及节点侧写法
- `docs/api-reference.md` / `README.md` / `docs/technical-design.md` §8 / `src/server/.env.example`:同步说明

客户配置(以 `/akm` 为例)只有三处:

```bash
# 1) Hub 侧
AKM_ROOT_PATH=/akm

# 2) 反向代理(nginx;两种写法二选一)
location /akm/ { proxy_pass http://hub:8000/; }   # 剥离前缀
# 或 location /akm/ { proxy_pass http://hub:8000; }  # 保留前缀(同样支持)

# 3) 节点侧(每台知识源机器)
AKM_HUB_API_URL=https://xx.com/akm/api
AKM_HUB_URL=wss://xx.com/akm/ws
```

WebSocket 需代理层升级头(`proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`),nginx 的 `location /akm/` 已同时覆盖 `/akm/ws`(实测 `/akm/ws` 升级返回 101)。

## 8. 节点侧(无代码改动)

`_derive_ws_url` 只剥末尾的 `/api` 再拼 `/ws`,前缀被完整保留:

```
https://xx.com/akm/api  ->  wss://xx.com/akm/ws     ✓
https://xx.com/a/b/api  ->  wss://xx.com/a/b/ws     ✓
```

仅文档说明;并补一条单测锁住子路径推导行为(防回归)。

## 9. 测试策略

**server pytest**(`tests/test_subpath_deployment.py`,34 项):

- `normalize_root_path` / `Settings` 各种输入(`""` / `/` / `akm` / `/akm/` / `/a/b/` / 含空白)
- 注入产物:含 `<base href="/akm/">` 与 `window.__AKM_BASE__ = "/akm/"`;根路径时二者为 `/`;不改写原有内容
- 两种代理写法下的路由匹配(以 ASGI scope 直接调用:path 带/不带前缀均 200)
- `GET {prefix}/` 与 `{prefix}/knowledge` 均返回注入后的 index.html;`/index.html` 只注入一次
- 静态资源在三种 `root_path` × 两种反代写法下全 200(锁住 §3.1 的回归)
- `resolve_static_file` 的目录穿越防护
- MCP:断言 `SseServerTransport` 的端点常量与真实注册路由一致(经 `app.openapi()["paths"]`)+ 传输实例 `_endpoint` 与常量一致

**web**(`tests/runtime-base.test.ts`,9 项):`normalizeBase` 归一化、`withBase` 拼接、`window.__AKM_BASE__` 缺失/根/单层/多层/非规范写法下的 `BASE_PATH` 与 `API_BASE`;`npm run build` 通过且产物中资源引用为 `./assets/*`。

**node**(`tests/test_login_urls.py`,8 项):`_derive_ws_url` 在根路径 / 单层 / 多层 / 带尾斜杠 / 含空格 / 前缀本身叫 `api` 六类输入下的结果。

**端到端(实测)**:临时 Hub 分别以 `AKM_ROOT_PATH=""`、`=/akm`、`=/a/b/c` 起:

- `{prefix}/` 返回注入后的 HTML(含 `<base href="{prefix}/">`)、`{prefix}/api/health` 200、`{prefix}/assets/*` 200、`{prefix}/vault.svg` 200、SPA 深链 `{prefix}/knowledge` 返回注入版 index.html
- `{prefix}/openapi.json` 的 `servers` 为 `[{"url": "{prefix}"}]`
- `{prefix}/ws` 升级返回 101
- SSE 通告 `{prefix}/api/mcp/messages`,按通告地址 POST → **202**(修复前为 404)
- 同时以**裸路径**(`/api/health`、`/assets/*`、`/knowledge`)请求全部 200 —— 等价于"代理剥离前缀"写法
- 启动日志打印生效前缀

## 10. 未采用的方案

| 方案 | 为什么不用 |
| --- | --- |
| 构建期写死 `VITE_BASE_PATH` | 前缀部署前不可知,等于每个客户构建一份 |
| 只靠代理 `sub_filter` 改写 HTML | 依赖 nginx 模块、脆弱;资源引用还可能是 JS 内动态拼接 |
| `HashRouter`(`xx.com/akm/#/knowledge`) | 破坏 URL 深链(搜索跳转/深链逐层展开是既有能力),分享链接变成带 `#` 的形态 |
| 要求客户把服务部署在域名根路径 | 现实不可行 —— 客户通常只有一个域名且已被其它系统占用 |
| uvicorn `--root-path` | 只支持"代理剥离前缀"一种写法,且要改 Dockerfile CMD |
| 保留 `app.mount("/assets", StaticFiles(...))` | 挂载点被追加进子 scope 的 `root_path`,"剥离前缀"写法下解析成 `static/assets/assets/x.js` 而 404(见 §3.1) |
| 用 `document.baseURI` 反推基址 | dev server 下等于当前路由 URL,会把路由段误当基址;react-router `basename` 也不读它 |
| 只注入 `<base>`,JS 侧自行相对解析 | fetch 的绝对路径不读 `<base>`;且动态拼接的 URL 极易漏改 |
