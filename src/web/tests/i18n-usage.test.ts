/** i18n 使用侧守卫(对应 openspec `web-i18n` 的 Translation Coverage / Language Packs Parity)。
 *
 * 覆盖三件事,均可在无浏览器环境下全量核验:
 * 1. 无裸 key —— 源码里每个 `t('...')` 字面量 key 都能在 zh 包解析到;
 * 2. 无硬编码文案 —— `src/`(除 `src/i18n/` 语言包)不存在含中日韩字符的字符串字面量;
 * 3. 相对时间文案随语言变化 —— `formatRelative` 不含硬编码中文,由注入的 `t` 决定输出。
 */
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import zh from '../src/i18n/zh'
import en from '../src/i18n/en'
import { formatRelative } from '../src/utils/format'

type LangPack = Record<string, unknown>

const SRC = resolve(__dirname, '../src')
const I18N_DIR = resolve(SRC, 'i18n')
const CJK = /[\u4e00-\u9fff]/

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) {
      if (full !== I18N_DIR) walk(full, out)
    } else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) {
      out.push(full)
    }
  }
  return out
}

function resolveKey(pack: LangPack, key: string): unknown {
  return key.split('.').reduce<unknown>((acc, part) => {
    if (acc && typeof acc === 'object') return (acc as LangPack)[part]
    return undefined
  }, pack)
}

/** 收集源码里 `t('key')` / `t("key")` 的字面量 key(动态拼接的 key 不参与) */
function usedKeys(): Map<string, Set<string>> {
  const found = new Map<string, Set<string>>()
  for (const file of walk(SRC)) {
    const text = readFileSync(file, 'utf-8')
    const re = /\bt\(\s*(['"])([A-Za-z0-9_.-]+)\1/g
    let m: RegExpExecArray | null
    while ((m = re.exec(text)) !== null) {
      const set = found.get(m[2]) ?? new Set<string>()
      set.add(file.slice(SRC.length + 1).replace(/\\/g, '/'))
      found.set(m[2], set)
    }
  }
  return found
}

/** 逐字符切分注释与字符串,返回含中日韩字符的字符串字面量(含所在行号) */
function cjkLiterals(text: string): { line: number; value: string }[] {
  const out: { line: number; value: string }[] = []
  let i = 0
  let line = 1
  while (i < text.length) {
    const c = text[i]
    if (c === '\n') {
      line++
      i++
    } else if (c === '/' && text[i + 1] === '/') {
      while (i < text.length && text[i] !== '\n') i++
    } else if (c === '/' && text[i + 1] === '*') {
      i += 2
      while (i < text.length && !(text[i] === '*' && text[i + 1] === '/')) {
        if (text[i] === '\n') line++
        i++
      }
      i += 2
    } else if (c === "'" || c === '"' || c === '`') {
      const quote = c
      const start = line
      let value = ''
      i++
      while (i < text.length) {
        if (text[i] === '\\') {
          value += text[i] + text[i + 1]
          i += 2
          continue
        }
        if (text[i] === quote) {
          i++
          break
        }
        if (text[i] === '\n') line++
        value += text[i]
        i++
      }
      if (CJK.test(value)) out.push({ line: start, value })
    } else {
      i++
    }
  }
  return out
}

/** 用语言包模拟 i18next 的 t(key, options)(支持 {{var}} 插值) */
function makeT(pack: LangPack) {
  return (key: string, options?: Record<string, unknown>): string => {
    const raw = resolveKey(pack, key)
    if (typeof raw !== 'string') return key
    if (!options) return raw
    return Object.entries(options).reduce(
      (acc, [k, v]) => acc.split(`{{${k}}}`).join(String(v)),
      raw,
    )
  }
}

describe('i18n 使用侧覆盖', () => {
  it('源码中每个 t() 字面量 key 都能在 zh 包解析到(无裸 key)', () => {
    const missing = [...usedKeys().entries()]
      .filter(([key]) => typeof resolveKey(zh as LangPack, key) !== 'string')
      .map(([key, files]) => `${key}  ← ${[...files].join(', ')}`)

    expect(missing, `以下 key 在 zh 包中缺失(运行时会显示裸 key):\n${missing.join('\n')}`).toEqual([])
  })

  it('核验覆盖度:确实扫到了足量 t() 调用', () => {
    expect(usedKeys().size).toBeGreaterThan(50)
  })
})

describe('i18n 硬编码守卫', () => {
  it('src/(除语言包)不存在含中文的字符串字面量', () => {
    const offenders: string[] = []
    for (const file of walk(SRC)) {
      const rel = file.slice(SRC.length + 1).replace(/\\/g, '/')
      for (const hit of cjkLiterals(readFileSync(file, 'utf-8'))) {
        offenders.push(`${rel}:${hit.line}  ${JSON.stringify(hit.value)}`)
      }
    }

    expect(
      offenders,
      `以下位置硬编码了用户可见中文,应改走 t():\n${offenders.join('\n')}`,
    ).toEqual([])
  })
})

describe('formatRelative 走 i18n', () => {
  const tZh = makeT(zh as LangPack)
  const tEn = makeT(en as LangPack)
  const now = Date.parse('2026-09-17T12:00:00Z')
  const ago = (seconds: number) => new Date(now - seconds * 1000).toISOString()

  it('缺失/非法时间回退为占位符', () => {
    expect(formatRelative(null, tZh)).toBe('-')
    expect(formatRelative('not-a-date', tZh)).toBe('-')
  })

  it('中文包输出中文相对时间', () => {
    expect(formatRelative(ago(30), tZh, now)).toBe('刚刚')
    expect(formatRelative(ago(5 * 60), tZh, now)).toBe('5 分钟前')
    expect(formatRelative(ago(3 * 3600), tZh, now)).toBe('3 小时前')
    expect(formatRelative(ago(2 * 86400), tZh, now)).toBe('2 天前')
  })

  it('英文包输出英文相对时间(证明文案未硬编码)', () => {
    expect(formatRelative(ago(30), tEn, now)).toBe('Just now')
    expect(formatRelative(ago(5 * 60), tEn, now)).toBe('5 min ago')
    expect(formatRelative(ago(3 * 3600), tEn, now)).toBe('3 h ago')
    expect(formatRelative(ago(2 * 86400), tEn, now)).toBe('2 d ago')
  })

  it('超过 30 天回退为本地日期,不再走相对文案', () => {
    const old = ago(45 * 86400)
    expect(formatRelative(old, tZh, now)).toBe(new Date(old).toLocaleDateString())
  })
})
