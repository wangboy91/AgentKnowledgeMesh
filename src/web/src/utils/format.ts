/**
 * 公共格式化工具:日期/大小/路径
 */
export function formatSize(bytes: number): { value: string; unit: string } {
  if (bytes < 1024) return { value: bytes.toFixed(0), unit: 'B' }
  if (bytes < 1024 * 1024) return { value: (bytes / 1024).toFixed(1), unit: 'KB' }
  if (bytes < 1024 * 1024 * 1024) return { value: (bytes / 1024 / 1024).toFixed(1), unit: 'MB' }
  return { value: (bytes / 1024 / 1024 / 1024).toFixed(1), unit: 'GB' }
}

export function formatDate(iso: string | null | undefined, fallback = '-'): string {
  if (!iso) return fallback
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return fallback
  return d.toLocaleString()
}

/**
 * 翻译函数签名(与 i18next 的 `t` 兼容)。
 *
 * utils 层不 import i18n 运行时,文案一律由调用侧注入,以满足
 * 「语言包之外不得硬编码用户可见文案」(openspec `web-i18n`)。
 */
export type Translator = (key: string, options?: Record<string, unknown>) => string

/** 相对时间文案:刚刚 / N 分钟前 / N 小时前 / N 天前;超过 30 天回退为本地日期。 */
export function formatRelative(
  iso: string | null | undefined,
  t: Translator,
  now = Date.now(),
): string {
  if (!iso) return '-'
  const ts = new Date(iso).getTime()
  if (Number.isNaN(ts)) return '-'
  const diff = (now - ts) / 1000
  if (diff < 60) return t('common.justNow')
  if (diff < 3600) return t('common.minutesAgo', { n: Math.floor(diff / 60) })
  if (diff < 86400) return t('common.hoursAgo', { n: Math.floor(diff / 3600) })
  if (diff < 86400 * 30) return t('common.daysAgo', { n: Math.floor(diff / 86400) })
  return new Date(iso).toLocaleDateString()
}

/** 把文件路径转成面包屑段 */
export function pathToSegments(filePath: string): string[] {
  return filePath.split('/').filter(Boolean)
}

/**
 * 把文档路径编码为 URL 路径:逐段 encodeURIComponent,保留 `/` 分隔。
 *
 * 文件名可能含 `#` `?` `%` 等 URL 特殊字符(三平台均允许),直接拼进
 * `/knowledge/...` 会被 react-router 的 parsePath 截断成 hash/search 或
 * 触发非法百分号编码;读取侧 useParams 会自动逐段解码,故只需构造侧编码。
 */
export function encodeDocPath(path: string): string {
  return path
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}
