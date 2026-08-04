import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Document } from '../api/client'

interface Props {
  document: Document
}

export default function MarkdownViewer({ document }: Props) {
  const sizeKB = (document.size / 1024).toFixed(1)
  const updated = new Date(document.updated_at).toLocaleString()

  return (
    <div className="doc-viewer">
      <div className="doc-header">
        <h1>{document.title}</h1>
        <div className="doc-meta">
          📄 {document.path} &nbsp;·&nbsp; {sizeKB} KB &nbsp;·&nbsp; Updated: {updated}
          {document.tags.length > 0 && (
            <>
              &nbsp;·&nbsp;
              {document.tags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    background: 'var(--bg-tertiary)',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    marginRight: '4px',
                  }}
                >
                  {tag}
                </span>
              ))}
            </>
          )}
        </div>
      </div>

      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {document.content || ''}
        </ReactMarkdown>
      </div>
    </div>
  )
}
