/**
 * 部署运行时基址(subpath-deployment)。
 *
 * 服务端在 index.html 注入 `window.__AKM_BASE__` 后,前端所有绝对路径
 * (API 基址、路由 basename)都必须带上该前缀,否则子路径部署下会打到域名根。
 * 这里锁定三件事:归一化规则、注入值优先、缺省不改变既有行为。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { normalizeBase, withBase } from '../src/runtime'

describe('normalizeBase', () => {
  it('空值 / 根路径 → `/`', () => {
    expect(normalizeBase('')).toBe('/')
    expect(normalizeBase('/')).toBe('/')
    expect(normalizeBase('///')).toBe('/')
    expect(normalizeBase(undefined)).toBe('/')
    expect(normalizeBase(null)).toBe('/')
    expect(normalizeBase('   ')).toBe('/')
  })

  it('补齐首尾斜杠', () => {
    expect(normalizeBase('akm')).toBe('/akm/')
    expect(normalizeBase('/akm')).toBe('/akm/')
    expect(normalizeBase('akm/')).toBe('/akm/')
    expect(normalizeBase('/akm/')).toBe('/akm/')
  })

  it('压缩重复斜杠并保留层级', () => {
    expect(normalizeBase('/akm//')).toBe('/akm/')
    expect(normalizeBase('//a//b//c//')).toBe('/a/b/c/')
    expect(normalizeBase('  /a/b/c  ')).toBe('/a/b/c/')
  })
})

describe('withBase', () => {
  it('根路径部署下原样返回', () => {
    // 本测试文件未注入 window.__AKM_BASE__,vite dev 的 BASE_URL 为 `/`
    expect(withBase('/api')).toBe('/api')
    expect(withBase('api')).toBe('/api')
    expect(withBase('/')).toBe('/')
  })

  it('拼接前缀且不产生重复斜杠', () => {
    expect(withBase('/api/documents')).toBe('/api/documents')
  })
})

describe('注入值优先', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  async function loadWith(injected?: string) {
    vi.resetModules()
    vi.stubGlobal('window', injected === undefined ? {} : { __AKM_BASE__: injected })
    return import('../src/runtime')
  }

  it('读取 window.__AKM_BASE__ 作为基址', async () => {
    const mod = await loadWith('/akm/')
    expect(mod.BASE_PATH).toBe('/akm/')
    expect(mod.API_BASE).toBe('/akm/api')
    expect(mod.withBase('/assets/x.js')).toBe('/akm/assets/x.js')
  })

  it('支持多层前缀', async () => {
    const mod = await loadWith('/a/b/c/')
    expect(mod.BASE_PATH).toBe('/a/b/c/')
    expect(mod.API_BASE).toBe('/a/b/c/api')
  })

  it('注入值写法不规范也能容错', async () => {
    const mod = await loadWith('akm')
    expect(mod.BASE_PATH).toBe('/akm/')
    expect(mod.API_BASE).toBe('/akm/api')
  })

  it('未注入时退回根路径(与引入本能力前行为一致)', async () => {
    const mod = await loadWith(undefined)
    expect(mod.BASE_PATH).toBe('/')
    expect(mod.API_BASE).toBe('/api')
  })
})
