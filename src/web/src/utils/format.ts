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

export function formatRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '-'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '-'
  const diff = (now - t) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
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
