/**
 * stripLeadingTitle:正文与文档标题去重
 *
 * 背景:document.title 由正文首个 `# ` 行提取,阅读视图头部据此渲染 h1,
 * 正文若原样渲染同一标题会出现两次(openspec `knowledge-browsing`
 * 「文档视图头部信息不重复」)。
 *
 * 剥离条件必须收窄——只认"开头处、与标题完全一致的一级标题",否则会误删
 * 刻意分节的正文标题。
 */
import { describe, it, expect } from 'vitest'
import { stripLeadingTitle } from '../src/utils/markdown'

describe('stripLeadingTitle', () => {
  it('首行与标题一致时剥离该行', () => {
    const content = '# 能力规格\n\n## Purpose\n\n正文\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe('## Purpose\n\n正文\n')
  })

  it('前导空行不影响判定', () => {
    const content = '\n\n# 能力规格\n\n正文\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe('正文\n')
  })

  it('标题两端空白差异视为一致', () => {
    expect(stripLeadingTitle('#   能力规格  \n正文', ' 能力规格 ')).toBe('正文')
  })

  it('首行标题与文档标题不一致时原样返回', () => {
    const content = '# 另一个标题\n\n正文\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe(content)
  })

  it('首行不是一级标题时原样返回', () => {
    const content = '## 二级标题\n\n正文\n'
    expect(stripLeadingTitle(content, '二级标题')).toBe(content)
  })

  it('正文中间的 H1 一律保留', () => {
    const content = '开头段落\n\n# 能力规格\n\n正文\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe(content)
  })

  it('标题来自文件名(正文无 H1)时原样返回', () => {
    const content = '只有正文,没有标题行\n'
    expect(stripLeadingTitle(content, 'spec')).toBe(content)
  })

  it('标题为空时原样返回(避免误删空标题行)', () => {
    const content = '# \n正文\n'
    expect(stripLeadingTitle(content, '')).toBe(content)
  })

  it('空内容与纯空行内容原样返回', () => {
    expect(stripLeadingTitle('', '标题')).toBe('')
    expect(stripLeadingTitle('\n\n', '标题')).toBe('\n\n')
  })

  it('`#` 后无空格不算一级标题', () => {
    const content = '#能力规格\n正文\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe(content)
  })

  it('CRLF 正文同样适用(行尾统一为 LF,渲染无差异)', () => {
    const content = '# 能力规格\r\n\r\n正文\r\n'
    expect(stripLeadingTitle(content, '能力规格')).toBe('正文\n')
  })

  it('整篇只有标题时返回空串', () => {
    expect(stripLeadingTitle('# 能力规格\n', '能力规格')).toBe('')
  })
})
