/**
 * Markdown 阅读器
 * - 顶部 breadcrumb(路径逐段可点击)—— 完整路径的**唯一载体**,meta 行不再重复
 * - 标题 + meta(来源 / size / updated / tags / RAG status)
 * - 正文 markdown-body(使用我们规范定义的样式);与标题重复的首个 H1 会被剥离
 */
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Document } from '../api/client'
import { formatSize, formatDate, pathToSegments, encodeDocPath } from '../utils/format'
import { stripLeadingTitle } from '../utils/markdown'
import {
  ClockIcon,
  CheckIcon,
  HourglassIcon,
  BanIcon,
  MinusIcon,
  HomeIcon,
  GlobeIcon,
} from './Icon'

interface Props {
  document: Document
  /** 归属节点的名称(仅当文档来自节点时由调用方解析传入;取不到则回退 node_id) */
  nodeName?: string | null
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
    not_indexed: {
      icon: <MinusIcon size={12} />,
      label: 'RAG',
      cls: 'badge--muted',
      titleKey: 'knowledge.ragNotIndexed',
    },
    excluded: {
      icon: <BanIcon size={12} />,
      label: 'RAG',
      cls: 'badge--muted',
      titleKey: 'knowledge.ragExcluded',
    },
  } as const
  const s = map[status ?? 'not_indexed']
  return { ...s, status: status ?? 'not_indexed' }
}

export default function MarkdownViewer({ document, nodeName }: Props) {
  const { t } = useTranslation()
  const size = formatSize(document.size)
  const updated = formatDate(document.updated_at)
  const breadcrumb = pathToSegments(document.path)
  const status = ragBadge(document.rag_status)

  // 处理 h1 标题:从第一段或正文中推断(保留)
  const cleanedTitle = useMemo(() => {
    return document.title || breadcrumb[breadcrumb.length - 1] || document.path
  }, [document.title, breadcrumb, document.path])

  // 正文首个 H1 与标题同源(入库时即由它提取),渲染前剥离以免标题出现两次
  const body = useMemo(
    () => stripLeadingTitle(document.content ?? '', cleanedTitle),
    [document.content, cleanedTitle],
  )

  // 文档来源:本机(Hub 自身扫描的目录)或某个接入节点
  const isLocal = document.node_id === 'local'
  const sourceLabel = isLocal ? t('knowledge.sourceLocal') : nodeName || document.node_id

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
                    <Link to={`/knowledge/${encodeDocPath(pathSoFar)}`}>{segment}</Link>
                  )}
                </span>
              )
            })}
          </nav>

          <h1>{cleanedTitle}</h1>

          <div className="doc-header__meta">
            {/* 路径已由上方面包屑承载,此处改标文档来源 */}
            <span className="doc-header__meta-item" title={`${t('knowledge.source')}: ${sourceLabel}`}>
              {isLocal ? <HomeIcon /> : <GlobeIcon />}
              <span className="truncate" style={{ maxWidth: 200 }}>{sourceLabel}</span>
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
            {body || `*${t('knowledge.emptyContent')}*`}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  )
}
