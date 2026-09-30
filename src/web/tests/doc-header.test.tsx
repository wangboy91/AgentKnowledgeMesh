/**
 * 文档视图头部:信息不重复(openspec `knowledge-browsing`「文档视图头部信息不重复」)
 *
 * 用 react-dom/server 静态渲染**真实组件**,断言输出 HTML 而不是源码——
 * 覆盖三条要求:标题只渲染一次、完整路径只由面包屑承载、meta 行标识文档来源。
 */
import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
// 副作用导入:初始化 i18next 实例(应用在 main.tsx 做,测试里需自行引入,
// 否则 useTranslation 解析不到 key、渲染出裸 key)
import '../src/i18n'
import MarkdownViewer from '../src/components/MarkdownViewer'
import type { Document } from '../src/api/client'

const PATH = 'AgentKnowledgeMesh/openspec/specs/document-conversion/spec.md'
const TITLE = 'document-conversion 能力规格'

function makeDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: 2,
    node_id: 'local',
    path: PATH,
    title: TITLE,
    hash: 'h',
    size: 2501,
    tags: [],
    rag_status: 'not_indexed',
    created_at: '2026-09-30T00:00:00',
    updated_at: '2026-09-30T00:00:00',
    content: `# ${TITLE}\n\n## Purpose\n\n正文段落\n`,
    ...overrides,
  }
}

function render(doc: Document, nodeName?: string | null): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <MarkdownViewer document={doc} nodeName={nodeName} />
    </MemoryRouter>,
  )
}

function count(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1
}

describe('文档视图头部', () => {
  it('正文首个 H1 与标题同源时被剥离,标题只出现一次', () => {
    const html = render(makeDoc())
    expect(count(html, TITLE)).toBe(1)
  })

  it('完整路径不出现在 meta 行(只由面包屑逐段承载)', () => {
    const html = render(makeDoc())
    expect(count(html, PATH)).toBe(0)
    // 面包屑逐段仍在,导航能力不丢
    for (const segment of ['AgentKnowledgeMesh', 'openspec', 'specs', 'document-conversion', 'spec.md']) {
      expect(html).toContain(segment)
    }
  })

  it('正文首个 H1 与标题不一致时保留(不误删)', () => {
    const html = render(makeDoc({ content: '# 另一个标题\n\n正文\n' }))
    expect(count(html, '另一个标题')).toBe(1)
    expect(count(html, TITLE)).toBe(1)
  })

  it('正文中间的一级标题保留', () => {
    const html = render(makeDoc({ content: '开头段落\n\n# 章节标题\n\n正文\n' }))
    expect(count(html, '章节标题')).toBe(1)
  })

  it('本机文档来源显示为「本机」', () => {
    const html = render(makeDoc({ node_id: 'local' }))
    expect(html).toContain('本机')
  })

  it('节点文档来源显示节点名', () => {
    const html = render(makeDoc({ node_id: 'node-1' }), 'WANG-Work-PC')
    expect(html).toContain('WANG-Work-PC')
    expect(html).not.toContain('本机')
  })

  it('节点名解析不到时回退节点标识', () => {
    const html = render(makeDoc({ node_id: 'node-1' }), null)
    expect(html).toContain('node-1')
  })
})
