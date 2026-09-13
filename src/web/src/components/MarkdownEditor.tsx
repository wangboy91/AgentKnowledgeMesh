import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import MDEditor from '@uiw/react-md-editor'
import { Document } from '../api/client'

interface Props {
  document: Document
  onSave: (content: string) => Promise<void>
  onCancel: () => void
}

export default function MarkdownEditor({ document, onSave, onCancel }: Props) {
  const { t } = useTranslation()
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
      alert(t('editor.saveFailed', { msg: (error as Error).message }))
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
          <span className="editor-title">{t('editor.title', { title: document.title })}</span>
          {hasChanges && <span className="editor-changed">{t('editor.modified')}</span>}
        </div>

        <div className="editor-actions">
          <button
            className="btn btn-save"
            onClick={handleSave}
            disabled={!hasChanges || saving}
          >
            {saving ? t('editor.saving') : t('editor.save')}
          </button>
          <button className="btn btn-cancel" onClick={onCancel}>
            {t('editor.cancel')}
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
        <span>{t('editor.pathLabel', { path: document.path })}</span>
        <span>{t('editor.sizeLabel', { size: (content.length / 1024).toFixed(1) })}</span>
        <span>{t('editor.shortcuts')}</span>
      </div>
    </div>
  )
}
