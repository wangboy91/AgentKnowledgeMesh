/**
 * Markdown 渲染前的正文整理(纯函数,便于单测)。
 */

/**
 * 剥离与文档标题重复的首个一级标题行。
 *
 * 文档标题在入库时即从正文首个 `# ` 行提取(knowledge-indexing「文档标题提取」),
 * 阅读视图的头部又据此渲染 h1 —— 正文若原样渲染,同一个标题会在页面上出现两次。
 *
 * 只剥离开头处**与标题完全一致**的 ATX 一级标题;条件刻意收窄以免误伤:
 * 标题来自文件名(正文无 `# ` 行)、正文刻意以别的 H1 开篇、或正文中间另有 H1 时,
 * 一律原样返回。
 *
 * @param content 文档正文(原始 Markdown)
 * @param title   文档标题(document.title)
 */
export function stripLeadingTitle(content: string, title: string): string {
  if (!content) return content
  const wanted = title.trim()
  if (!wanted) return content

  const lines = content.split(/\r?\n/)

  // 前导空行不算"首个非空行"
  let start = 0
  while (start < lines.length && lines[start].trim() === '') start++
  const first = lines[start]
  if (first === undefined) return content

  const matched = /^#\s+(.*)$/.exec(first.trim())
  if (!matched || matched[1].trim() !== wanted) return content

  // 标题行之后紧跟的空行一并去掉,避免正文顶部多出一段空白
  let rest = start + 1
  while (rest < lines.length && lines[rest].trim() === '') rest++
  return lines.slice(rest).join('\n')
}
