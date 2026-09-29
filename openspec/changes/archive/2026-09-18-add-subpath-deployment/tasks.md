# subpath-deployment · 任务清单

## 1. 服务端配置与 root_path

- [x] 1.1 `src/server/app/config.py`:新增 `root_path` 设置(`AKM_ROOT_PATH`,默认空)与纯函数 `normalize_root_path(raw)`(补前导斜杠、去尾部斜杠、`/` 归一为空);验证:单测覆盖 `""` / `"/"` / `"akm"` / `"/akm/"` / `"/a/b/"` / 含空白 六种输入
- [x] 1.2 `src/server/app/main.py`:`FastAPI(root_path=settings.root_path)`;验证:直接以 ASGI scope 调用,`path` 带前缀与不带前缀两种情形均命中 `/api/health`(两种反代写法都支持)
- [x] 1.3 启动日志打印生效的根路径(空时提示"根路径部署");验证:三种配置下启动日志实测 —— `🔗 Deploy root path: /akm (经反向代理子路径访问)` / `/ (域名根路径)` / `/a/b/c (经反向代理子路径访问)`

## 2. index.html 运行时注入

- [x] 2.1 新增 `render_index_html()`:读 `static/index.html`,在 `<head>` 后注入 `<base href="{root}/" />` 与 `<script>window.__AKM_BASE__ = "{root}/";</script>`;`create_app()` 时渲染一次并缓存;验证:单测断言三种 `root_path` 下的注入产物内容 + 不改写原文
- [x] 2.2 SPA catch-all 改为:命中静态真实文件(非 index.html)→ `FileResponse` 原样返回;否则 → 注入后的 `HTMLResponse`(带 `Cache-Control: no-cache`);验证:单测 + 实测 `/akm/`、`/akm/knowledge` 均返回注入版、静态文件返回 etag 原样内容
- [x] 2.3 确认静态目录不存在(未构建前端)时行为不变;验证:单测覆盖(`index_html is None` 分支回退 `FileResponse(index_path)`)
- [x] 2.4 **(顺带修正)** 移除 `app.mount("/assets", StaticFiles(...))`,静态文件统一由 catch-all 解析:Mount 会把挂载点追加进 `scope["root_path"]`,代理剥离前缀时被解析成 `static/assets/assets/x.js` 而 404;验证:单测 `test_assets_reachable_in_both_proxy_modes`(三种 root_path × 两种写法全 200)+ 实测
- [x] 2.5 **(顺带加固)** 静态解析加目录穿越防护(`resolve_static_file()`:resolve 后校验仍在 `static/` 内);验证:单测 5 项 + 实测 `..%2F..%2Fapp%2Fconfig.py` 未泄露源码

## 3. MCP SSE 端点修正

- [x] 3.1 `src/server/app/api/mcp.py`:`SseServerTransport("/messages")` → `SseServerTransport("/api/mcp/messages")`;验证:临时 Hub 实测 SSE 通告 `data: /api/mcp/messages?session_id=...`,按通告地址 POST 返回 202(修复前为 404)
- [x] 3.2 加断言测试:SSE 通告端点常量必须与真实注册路由一致(`app.openapi()["paths"]`,顶层 `app.routes` 被惰性 `_IncludedRouter` 包住取不到)+ 传输实例 `_endpoint` 与常量一致;验证:`pytest tests/test_subpath_deployment.py` 通过
- [x] 3.3 子路径下实测 SSE 通告为 `{prefix}/api/mcp/messages`;验证:`AKM_ROOT_PATH=/akm` 起服务后实测通告 `/akm/api/mcp/messages?session_id=...`,按该地址 POST → **202**

## 4. 前端运行时基址

- [x] 4.1 `src/web/vite.config.ts`:`base: command === 'build' ? './' : '/'`;验证:`npm run build` 产物 index.html 中资源引用为 `./assets/*`
- [x] 4.2 新增 `src/web/src/runtime.ts`:导出 `BASE_PATH` / `API_BASE` / `withBase()` / `normalizeBase()`,读 `window.__AKM_BASE__` 并在缺失或非法时回退 vite `BASE_URL` → `'/'`;验证:`tests/runtime-base.test.ts` 9 项(归一化 / 缺省 / 注入优先 / 多层前缀 / 非规范写法)
- [x] 4.3 `src/web/src/main.tsx`:`<BrowserRouter basename={BASE_PATH}>`;验证:`npm run build`(tsc)通过;根路径下 basename 为 `'/'` 行为不变
- [x] 4.4 `src/web/src/api/client.ts`:`const BASE_URL = API_BASE`(替换写死的 `'/api'`);验证:构建通过 + 前端测试全绿
- [x] 4.5 `src/web/index.html`:favicon 改 `%BASE_URL%vault.svg`,并补 `src/web/public/vault.svg`(此前该文件不存在,根路径部署下也是 404);验证:构建产物含 `./vault.svg`,实测 `/akm/vault.svg` → 200 `image/svg+xml`

## 5. 部署配置与文档

- [x] 5.1 `deploy/docker-compose.yml` / `.pg.yml` / `.external-pg.yml` 的 `akm-hub.environment` 增加 `AKM_ROOT_PATH=${AKM_ROOT_PATH:-}`(build 叠加文件只改镜像来源,自动继承);验证:`docker compose config` 三种模式 + build 叠加全过,不设该变量时为空(行为不变),设 `/a/b/c` 时正确透传
- [x] 5.2 `deploy/.env.example` 新增第 4 节「子路径部署」(`AKM_ROOT_PATH` 说明 + nginx 两种写法 + Caddy 一行 + 层级示例),原 4~7 节顺延为 5~8;§8 节点补子路径地址写法;验证:变量名与 compose 一致
- [x] 5.3 `docs/deployment.md` 新增 §1.9 子路径部署:客户要配的三处(Hub / 反代 / 节点)、两种反代写法、WebSocket 升级头、任意层级、验证命令、注意事项;§1.3 变量表补行;§2.2 / §2.4 / §3 补前缀说明;§4 常见问题补两条
- [x] 5.4 `docs/api-reference.md`:补充"子路径部署时所有端点前缀为 `AKM_ROOT_PATH`,Swagger `servers` 自动带前缀";验证:表述与实测一致
- [x] 5.5 `README.md` 部署段加子路径入口 + 修正"dist 交由 Nginx 托管"的旧说法(入口必须经 Hub 注入);`docs/technical-design.md` §8 加同向注解;`src/server/.env.example` 第 1 节补 `AKM_ROOT_PATH`;`deploy/docker-compose.node.yml` 注释补子路径地址
- [x] 5.6 `.github/workflows/release.yml` 的 `files:` 已含 `deploy/.env.example`(上一轮完成),无需再改

## 6. 节点侧

- [x] 6.1 新增 `src/node/tests/test_login_urls.py` 覆盖 `_derive_ws_url` 子路径用例(单层 / 多层 / 带尾斜杠 / 含空格 / 前缀本身叫 api);验证:`pytest` 8 项通过(节点侧无代码改动 —— `hub_url` / `hub_api_url` 都是显式完整地址,前缀天然保留)
- [x] 6.2 `akm-node login` 交互提示补充子路径写法说明;验证:节点全量测试 61 项通过(无 stdout 断言被打破)

## 7. 端到端验证与收尾

- [x] 7.1 临时 Hub 以 `AKM_ROOT_PATH=""` 起:根路径下所有既有行为不变(`/`、`/api/health`、`/knowledge`、`/assets/*`、`/vault.svg` 全 200,注入 `<base href="/">`);验证:curl 逐项核对
- [x] 7.2 临时 Hub 以 `AKM_ROOT_PATH=/akm` 起:`/akm/` 200 且注入 `<base href="/akm/">`、`/akm/api/health` 200、`/akm/assets/*` 200、`/akm/vault.svg` 200、SPA 深链 `/akm/knowledge` 返回注入版 index.html、`/akm/openapi.json` 的 `servers=[{'url':'/akm'}]`、`/akm/ws` 升级返回 101、SSE 通告 `/akm/api/mcp/messages` 且 POST → 202;同时以**裸路径**请求(`/api/health`、`/assets/*`、`/knowledge`)全部 200,等价验证"代理剥离前缀"写法;验证:curl 逐项核对
- [x] 7.3 多层级验证 `AKM_ROOT_PATH=/a/b/c`:`/a/b/c/*` 与裸路径两套请求全部 200,深链注入 `<base href="/a/b/c/">`;验证:curl 逐项核对
- [x] 7.4 跑验证基线:`src/server` pytest **164 passed**(deselect 已知环境性失败 `test_ws_register_token_required`)、`src/web` vitest **23 passed** + `npm run build` 通过、`src/node` pytest **61 passed**;验证:全绿
- [x] 7.5 清理临时服务与探测脚本,确认无残留进程/端口;验证:三个临时 Hub 已停止 + 端口探测

## 8. 规格与归档

- [x] 8.1 `openspec validate 2026-09-18-add-subpath-deployment` 通过
- [x] 8.2 归档:delta spec 合入 `openspec/specs/`(`subpath-deployment` 新建 + `document-management` / `mcp-integration` 的 MODIFIED 已替换基线),变更目录移入 `openspec/changes/archive/`
