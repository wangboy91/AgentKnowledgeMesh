/**
 * Markdown 阅读器
 * - 顶部 breadcrumb(路径逐段可点击)
 * - 标题 + meta(path / size / updated / tags / RAG status)
 * - 正文 markdown-body(使用我们规范定义的样式)
 */
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Document } from '../api/client'
import { formatSize, formatDate, pathToSegments } from '../utils/format'
import {
  FileIcon,
  ClockIcon,
  CheckIcon,
  HourglassIcon,
  BanIcon,
} from './Icon'

interface Props {
  document: Document
}

function ragBadge(status: Document['rag_status']) {
  const map = {
    indexed: {
      icon: <CheckIcon size={12} />,
      label: 'RAG',
      cls: 'badge--success',
      titleKey: 'knowledge.ragIndexed',
    },
    pending: {
      icon: <HourglassIcon size={12} />,
      label: 'RAG',
      cls: 'badge--warning',
      titleKey: 'knowledge.ragPending',
    },
    excluded: {
      icon: <BanIcon size={12} />,
      label: 'RAG',
      cls: 'badge--muted',
      titleKey: 'knowledge.ragExcluded',
    },
  } as const
  const s = map[status ?? 'indexed']
  return { ...s, status: status ?? 'indexed' }
}

export default function MarkdownViewer({ document }: Props) {
  const { t } = useTranslation()
  const size = formatSize(document.size)
  const updated = formatDate(document.updated_at)
  const breadcrumb = pathToSegments(document.path)
  const status = ragBadge(document.rag_status)

  // 处理 h1 标题:从第一段或正文中推断(保留)
  const cleanedTitle = useMemo(() => {
    return document.title || breadcrumb[breadcrumb.length - 1] || document.path
  }, [document.title, breadcrumb, document.path])

  return (
    <div className="doc-viewer">
      <div className="doc-body doc-body--wide">
        <div className="doc-header">
          {/* breadcrumb */}
          <nav className="doc-header__breadcrumbs" aria-label={t('layout.breadcrumbs')}>
            {breadcrumb.map((segment, i) => {
              const isLast = i === breadcrumb.length - 1
              const pathSoFar = breadcrumb.slice(0, i + 1).join('/')
              return (
                <span key={pathSoFar} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  {i > 0 && <span className="doc-header__breadcrumbs__sep">/</span>}
                  {isLast ? (
                    <strong>{segment}</strong>
                  ) : (
                    <Link to={`/knowledge/${pathSoFar}`}>{segment}</Link>
                  )}
                </span>
              )
            })}
          </nav>

          <h1>{cleanedTitle}</h1>

          <div className="doc-header__meta">
            <span className="doc-header__meta-item" title={document.path}>
              <FileIcon />
              <span className="truncate" style={{ maxWidth: 280 }}>{document.path}</span>
            </span>
            <span className="doc-header__meta-item">
              <strong>{size.value}</strong>&nbsp;{size.unit}
            </span>
            <span className="doc-header__meta-item" title={updated}>
              <ClockIcon />
              <span>{updated}</span>
            </span>
            <span
              className={`badge ${status.cls}`}
              title={t(status.titleKey, { status: status.status })}
            >
              {status.icon}
              <span>{t(status.titleKey, { status: status.status })}</span>
            </span>
            {document.tags && document.tags.length > 0 && (
              <span className="doc-header__tags">
                {document.tags.map((tag) => (
                  <span key={tag} className="badge badge--accent">
                    #{tag}
                  </span>
                ))}
              </span>
            )}
          </div>
        </div>

        <article className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {document.content || `*${t('knowledge.emptyContent')}*`}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  )
}
