import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { api, Document } from '../api/client'
import MarkdownViewer from '../components/MarkdownViewer'

export default function Knowledge() {
  const { '*': filePath } = useParams<{ '*': string }>()
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (filePath) {
      loadDocument(filePath)
    } else {
      setDocument(null)
    }
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

  return <MarkdownViewer document={document} />
}
