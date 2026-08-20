import { useState, useEffect, useCallback } from 'react'
import MDEditor from '@uiw/react-md-editor'
import { Document } from '../api/client'

interface Props {
  document: Document
  onSave: (content: string) => Promise<void>
  onCancel: () => void
}

export default function MarkdownEditor({ document, onSave, onCancel }: Props) {
  const [content, setContent] = useState(document.content || '')
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  // 监听内容变化
  useEffect(() => {
    setHasChanges(content !== (document.content || ''))
  }, [content, document.content])

  // 保存
  const handleSave = useCallback(async () => {
    if (!hasChanges) return

    setSaving(true)
    try {
      await onSave(content)
    } catch (error) {
      console.error('Save failed:', error)
      alert('保存失败: ' + (error as Error).message)
    } finally {
      setSaving(false)
    }
  }, [content, hasChanges, onSave])

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + S 保存
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
      // Escape 取消
      if (e.key === 'Escape') {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, onCancel])

  return (
    <div className="editor-container">
      {/* 工具栏 */}
      <div className="editor-toolbar">
        <div className="editor-info">
          <span className="editor-title">编辑: {document.title}</span>
          {hasChanges && <span className="editor-changed">● 已修改</span>}
        </div>

        <div className="editor-actions">
          <button
            className="btn btn-save"
            onClick={handleSave}
            disabled={!hasChanges || saving}
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button className="btn btn-cancel" onClick={onCancel}>
            取消
          </button>
        </div>
      </div>

      {/* 编辑器 */}
      <div className="editor-body" data-color-mode="auto">
        <MDEditor
          value={content}
          onChange={(val) => setContent(val || '')}
          height="100%"
          preview="live"
          visibleDragbar={true}
        />
      </div>

      {/* 状态栏 */}
      <div className="editor-status">
        <span>路径: {document.path}</span>
        <span>大小: {(content.length / 1024).toFixed(1)} KB</span>
        <span>快捷键: Ctrl+S 保存, Esc 取消</span>
      </div>
    </div>
  )
}
