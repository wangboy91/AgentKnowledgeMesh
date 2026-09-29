/**
 * 部署运行时基址(subpath-deployment)。
 *
 * 服务端在 `index.html` 的 `<head>` 里注入两样东西(见 `server/app/main.py`
 * 的 `render_index_html`):
 *   1. `<base href="{前缀}/">` —— 让构建产物里的相对引用(`./assets/*`)解析到前缀下
 *   2. `window.__AKM_BASE__ = "{前缀}/"` —— 本模块读取的运行时基址
 *
 * 为什么两者都要,不能只留 `<base>`:
 * - `<base>` 只作用于**浏览器**对相对 URL 的解析,JS 里的 `fetch('/api/x')`
 *   是绝对路径,完全不受 `<base>` 影响;
 * - react-router 的 `basename` 不读 `document.baseURI`;
 * - vite dev server 下 `document.baseURI` 等于当前路由地址(如
 *   `http://localhost:5173/knowledge`),据此推断前缀会误判。
 *
 * 于是同一份前端构建产物可运行在任意深度的子路径下(`/`、`/akm/`、`/a/b/c/`),
 * 无需为每个前缀重新构建。
 */

declare global {
  interface Window {
    /** 服务端注入的部署前缀,形如 `/` 或 `/akm/` */
    __AKM_BASE__?: string
  }
}

/** 把任意写法的基址归一成 `/` 或 `/前缀/`(带首尾斜杠、无重复斜杠) */
export function normalizeBase(raw?: string | null): string {
  const value = (raw ?? '').trim()
  if (!value) return '/'
  const segments = value.split('/').filter(Boolean)
  return segments.length > 0 ? `/${segments.join('/')}/` : '/'
}

function resolveBase(): string {
  // 1) 服务端注入 —— 唯一权威来源
  const injected = typeof window !== 'undefined' ? window.__AKM_BASE__ : undefined
  if (injected) return normalizeBase(injected)

  // 2) vite 的 BASE_URL:dev 下为 `/`;生产构建用的是相对基路径 `./`,
  //    只在 index.html 由服务端注入时才成立,故此处不作为基址使用
  const viteBase = import.meta.env.BASE_URL
  if (viteBase && viteBase.startsWith('/')) return normalizeBase(viteBase)

  // 3) 兜底:根路径部署(与引入本能力前的行为一致)
  return '/'
}

/** 部署前缀,始终形如 `/` 或 `/akm/`(可直接用作 react-router 的 `basename`) */
export const BASE_PATH: string = resolveBase()

/**
 * 应用内绝对路径 → 带部署前缀的路径。
 *
 * `withBase('/api')` → `/akm/api`;根路径部署下原样返回。
 * 用于 API 基址、静态资源、WebSocket 等任何需要绝对路径的场景。
 */
export function withBase(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  if (normalized === '/') return BASE_PATH
  return `${BASE_PATH}${normalized.slice(1)}`
}

/** API 基址(不带尾斜杠),例如 `/api` 或 `/akm/api` */
export const API_BASE: string = withBase('/api')
