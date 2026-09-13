import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Document } from '../api/client'
import { useSelectedNodeId } from '../KnowledgeCtx'
import MarkdownViewer from '../components/MarkdownViewer'
import MarkdownEditor from '../components/MarkdownEditor'

export default function Knowledge() {
  const { t } = useTranslation()
  const { '*': filePath } = useParams<{ '*': string }>()
  const selectedNodeId = useSelectedNodeId()
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
    // 切换文档时退出编辑模式
    setEditing(false)
  }, [filePath, selectedNodeId])

  async function loadDocument(path: string) {
    setLoading(true)
    setError(null)
    try {
      // 先获取文档列表找到 ID
      const docs = await api.getDocuments()
      const doc = docs.find((d) => d.path === path)
      if (!doc) {
        setError(t('knowledge.documentNotFound'))
        return
      }
      // 获取完整内容
      const fullDoc = await api.getDocument(doc.id)
      // 防御:右栏文档不属于当前选中节点时清空回占位(仅具体节点生效)
      if (selectedNodeId && fullDoc.node_id !== selectedNodeId) {
        setDocument(null)
        return
      }
      setDocument(fullDoc)
    } catch (err) {
      setError(t('knowledge.loadFailed'))
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  // 保存文档
  async function handleSave(content: string) {
    if (!document) return

    const updated = await api.updateDocument(document.id, content)
    setDocument(updated)
    setEditing(false)
  }

  // 取消编辑
  function handleCancel() {
    setEditing(false)
  }

  // 加入/移出语义检索(admin)
  async function handleToggleRag() {
    if (!document) return
    const enable = document.rag_status === 'excluded'
    const updated = await api.setDocumentRag(document.id, enable)
    setDocument(updated)
  }

  if (!filePath) {
    return (
      <div className="empty-state">
        <span style={{ fontSize: '48px' }}>📚</span>
        <p>{t('knowledge.emptyHint')}</p>
      </div>
    )
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  if (error) {
    return (
      <div className="empty-state">
        <span style={{ fontSize: '48px' }}>❌</span>
        <p>{error}</p>
      </div>
    )
  }

  if (!document) {
    // 空态占位(含"文档不属于当前节点"的防御清空)
    return (
      <div className="empty-state">
        <span style={{ fontSize: '48px' }}>📚</span>
        <p>{t('knowledge.docUnavailable')}</p>
      </div>
    )
  }

  // 编辑模式
  if (editing) {
    return (
      <MarkdownEditor
        document={document}
        onSave={handleSave}
        onCancel={handleCancel}
      />
    )
  }

  // 查看模式 - 添加编辑按钮(仅 admin 可编辑,account-auth)
  return (
    <div className="knowledge-viewer">
      <div className="viewer-toolbar">
        {isAdmin() && (
          <>
            <button
              className="btn"
              onClick={handleToggleRag}
              title={t('knowledge.ragToggleHint')}
            >
              {document.rag_status === 'excluded'
                ? t('knowledge.addToRag')
                : document.rag_status === 'pending'
                  ? t('knowledge.indexing')
                  : t('knowledge.removeFromRag')}
            </button>
            <button
              className="btn btn-edit"
              onClick={() => setEditing(true)}
            >
              ✏️ 编辑
            </button>
          </>
        )}
      </div>
      <MarkdownViewer document={document} />
    </div>
  )
}
