/**
 * encodeDocPath:文档路径 → URL 路径段编码
 *
 * 背景:文件名可能含 `#` `?` `%` 等字符(三平台文件系统均允许),
 * 直接拼进 /knowledge/... 会被 react-router 的 parsePath 截断。
 * 读取侧 react-router matchRoutes 会逐段 decodeURIComponent,
 * 因此构造侧逐段编码即可无损往返。
 */
import { describe, it, expect } from 'vitest'
import { encodeDocPath } from '../src/utils/format'

/** 模拟 react-router matchRoutes 对 pathname 的逐段解码(见 @remix-run/router decodePath) */
function decodePathname(pathname: string): string {
  return pathname
    .split('/')
    .map((seg) => decodeURIComponent(seg).replace(/\//g, '%2F'))
    .join('/')
}

describe('encodeDocPath', () => {
  it('普通路径保持不变', () => {
    expect(encodeDocPath('projects/ai-crm.md')).toBe('projects/ai-crm.md')
  })

  it('编码 # 与 ?(否则被 parsePath 截断为 hash/search)', () => {
    expect(encodeDocPath('docs/what#anchor.md')).toBe('docs/what%23anchor.md')
    expect(encodeDocPath('docs/Q&A.md')).toBe('docs/Q%26A.md')
    expect(encodeDocPath('docs/when?.md')).toBe('docs/when%3F.md')
  })

  it('编码 %(否则形成非法百分号序列)', () => {
    expect(encodeDocPath('docs/100%_done.md')).toBe('docs/100%25_done.md')
  })

  it('编码空格与中文', () => {
    expect(encodeDocPath('docs/my notes/总结.md')).toBe('docs/my%20notes/%E6%80%BB%E7%BB%93.md')
  })

  it('与 react-router 读取侧解码往返无损', () => {
    const paths = [
      'projects/ai-crm.md',
      'docs/what#anchor.md',
      'docs/when?.md',
      'docs/100%_done.md',
      'docs/my notes/总结 & 备注.md',
      'a+b/c=d.md',
    ]
    for (const p of paths) {
      expect(decodePathname(encodeDocPath(p))).toBe(p)
    }
  })

  it('忽略空段(多斜杠/首尾斜杠)', () => {
    expect(encodeDocPath('/docs//a.md/')).toBe('docs/a.md')
  })
})
