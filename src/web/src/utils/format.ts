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
