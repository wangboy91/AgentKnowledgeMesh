import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { api, Document } from '../api/client'
import MarkdownViewer from '../components/MarkdownViewer'
import MarkdownEditor from '../components/MarkdownEditor'

export default function Knowledge() {
  const { '*': filePath } = useParams<{ '*': string }>()
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
  }, [filePath])

  async function loadDocument(path: string) {
    setLoading(true)
    setError(null)
    try {
      // 先获取文档列表找到 ID
      const docs = await api.getDocuments()
      const doc = docs.find((d) => d.path === path)
      if (!doc) {
        setError('Document not found')
        return
      }
      // 获取完整内容
      const fullDoc = await api.getDocument(doc.id)
      setDocument(fullDoc)
    } catch (err) {
      setError('Failed to load document')
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

  if (!filePath) {
    return (
      <div className="empty-state">
        <span style={{ fontSize: '48px' }}>📚</span>
        <p>Select a document from the file tree</p>
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
    return null
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

  // 查看模式 - 添加编辑按钮
  return (
    <div className="knowledge-viewer">
      <div className="viewer-toolbar">
        <button
          className="btn btn-edit"
          onClick={() => setEditing(true)}
        >
          ✏️ 编辑
        </button>
      </div>
      <MarkdownViewer document={document} />
    </div>
  )
}
