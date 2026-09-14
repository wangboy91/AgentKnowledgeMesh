/**
 * 知识库页:
 * - Topbar 已经包含 SearchBar(breadcrumbs 由 Layout 维护),并提供 Tree Pane 折叠按钮
 * - 主体:Tree Pane(由 Layout 通过 Context 控制显隐) + Document Pane
 * - 当 filePath 为空时,Doc Pane 显示引导选择态;加载/错误/不可用 各有专门 empty state
 */
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Document } from '../api/client'
import { useSelectedNodeId, useTreeVisible } from '../KnowledgeCtx'
import MarkdownViewer from '../components/MarkdownViewer'
import MarkdownEditor from '../components/MarkdownEditor'
import FileTree from '../components/FileTree'
import EmptyState from '../components/EmptyState'
import {
  EmptyDocIcon,
  AlertIcon,
  FileIcon,
} from '../components/Icon'
import { useToast, useErrorReporter } from '../components/Toast'
import { pathToSegments } from '../utils/format'

export default function Knowledge() {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
  const { '*': filePath } = useParams<{ '*': string }>()
  const selectedNodeId = useSelectedNodeId()
  const treeVisible = useTreeVisible()
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (filePath) {
      loadDocument(filePath)
    } else {
      setDocument(null)
    }
    setEditing(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filePath, selectedNodeId])

  async function loadDocument(path: string) {
    setLoading(true)
    setError(null)
    try {
      // 在选中节点作用域内按 path 查找;URL 会把 \ 规范化为 /,两侧统一归一化兜底
      const normalized = path.replace(/\\/g, '/')
      const docs = await api.getDocuments(selectedNodeId ?? undefined)
      const doc = docs.find((d) => d.path.replace(/\\/g, '/') === normalized)
      if (!doc) {
        setError(t('knowledge.documentNotFound'))
        return
      }
      const fullDoc = await api.getDocument(doc.id)
      if (selectedNodeId && fullDoc.node_id !== selectedNodeId) {
        setDocument(null)
        return
      }
      setDocument(fullDoc)
    } catch (err) {
      setError(t('knowledge.loadFailed'))
      reportError(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(content: string) {
    if (!document) return
    try {
      const updated = await api.updateDocument(document.id, content)
      setDocument(updated)
      setEditing(false)
      toast.success(t('editor.saved'))
    } catch (err) {
      reportError(err)
    }
  }

  function handleCancel() {
    setEditing(false)
  }

  async function handleToggleRag() {
    if (!document) return
    const enable = document.rag_status === 'excluded'
    try {
      const updated = await api.setDocumentRag(document.id, enable)
      setDocument(updated)
    } catch (err) {
      reportError(err)
    }
  }

  // ---------- Doc Pane 内容 ----------
  let docContent: React.ReactNode

  if (!filePath) {
    docContent = (
      <EmptyState
        icon={<EmptyDocIcon size={28} />}
        title={t('knowledge.emptyTitle')}
        desc={t('knowledge.emptyDesc')}
      />
    )
  } else if (loading) {
    docContent = (
      <EmptyState
        icon={<FileIcon size={28} />}
        title={t('common.loading')}
        desc={t('knowledge.loadingDesc')}
      />
    )
  } else if (error) {
    docContent = (
      <EmptyState
        variant="danger"
        icon={<AlertIcon size={28} />}
        title={t('knowledge.loadFailed')}
        desc={error}
        actions={
          <button className="btn" onClick={() => loadDocument(filePath)}>
            {t('common.retry')}
          </button>
        }
      />
    )
  } else if (!document) {
    docContent = (
      <EmptyState
        icon={<EmptyDocIcon size={28} />}
        title={t('knowledge.docUnavailable')}
        desc={t('knowledge.docUnavailableDesc')}
      />
    )
  } else if (editing) {
    docContent = (
      <MarkdownEditor document={document} onSave={handleSave} onCancel={handleCancel} />
    )
  } else {
    docContent = (
      <>
        {isAdmin() && (
          <div className="doc-toolbar">
            <button
              className="btn btn--ghost"
              onClick={handleToggleRag}
              title={t('knowledge.ragToggleHint')}
            >
              {document.rag_status === 'excluded'
                ? t('knowledge.addToRag')
                : document.rag_status === 'pending'
                  ? t('knowledge.indexing')
                  : t('knowledge.removeFromRag')}
            </button>
            <button className="btn btn--primary" onClick={() => setEditing(true)}>
              {t('common.edit')}
            </button>
          </div>
        )}
        <MarkdownViewer document={document} />
      </>
    )
  }

  return (
    <>
      {treeVisible && (
        <section className="tree-pane" aria-label={t('layout.paneTree')}>
          <div className="tree-pane__body">
            <FileTree />
          </div>
        </section>
      )}

      {/* Document Pane */}
      <section className="panel doc-viewer" aria-label={t('layout.paneDoc')}>
        {docContent}
      </section>
    </>
  )
}

/** 顶层知识库路由的 helper:面包屑首段不在 Knowledge 内部消费,这里仅占位 */
export function KnowledgeBreadcrumbFromPath(path: string): string[] {
  return pathToSegments(path)
}