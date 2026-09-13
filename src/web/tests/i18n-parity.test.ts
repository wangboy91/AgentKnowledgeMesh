/** i18n 语言包 parity 测试:zh/en 两包 key 集合必须一致. */
import { describe, expect, it } from 'vitest'
import zh from '../src/i18n/zh'
import en from '../src/i18n/en'

type LangPack = Record<string, unknown>

function leafKeys(obj: LangPack, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const p = prefix ? `${prefix}.${k}` : k
    return v !== null && typeof v === 'object' ? leafKeys(v as LangPack, p) : [p]
  })
}

describe('i18n parity', () => {
  it('zh/en 两包 key 集合完全一致', () => {
    const zk = leafKeys(zh).sort()
    const ek = leafKeys(en).sort()

    const missingInEn = zk.filter((k) => !ek.includes(k))
    const extraInEn = ek.filter((k) => !zk.includes(k))

    expect(
      missingInEn,
      `en 包缺少以下 key:\n${missingInEn.join('\n')}`,
    ).toEqual([])
    expect(
      extraInEn,
      `en 包存在而 zh 没有的 key:\n${extraInEn.join('\n')}`,
    ).toEqual([])
  })
})