/**
 * Markdown 编辑器 · 基于 @uiw/react-md-editor,统一外观到 design system
 * - 顶部 toolbar:文件名 + 修改指示 + 保存/取消
 * - 中部编辑区(跟随主题切换)
 * - 底部状态栏:路径、大小、快捷键
 */
import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import MDEditor from '@uiw/react-md-editor'
import { Document } from '../api/client'
import { useErrorReporter } from './Toast'
import { CheckIcon } from './Icon'

interface Props {
  document: Document
  onSave: (content: string) => Promise<void>
  onCancel: () => void
}

export default function MarkdownEditor({ document, onSave, onCancel }: Props) {
  const { t } = useTranslation()
  const reportError = useErrorReporter()
  const [content, setContent] = useState(document.content || '')
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    setHasChanges(content !== (document.content || ''))
  }, [content, document.content])

  const handleSave = useCallback(async () => {
    if (!hasChanges) return
    setSaving(true)
    try {
      await onSave(content)
    } catch (err) {
      reportError(err)
    } finally {
      setSaving(false)
    }
  }, [content, hasChanges, onSave, reportError])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, onCancel])

  return (
    <div className="editor-container">
      <div className="editor-toolbar">
        <div className="editor-info">
          <span className="editor-title">{t('editor.title', { title: document.title })}</span>
          {hasChanges && <span className="editor-changed">{t('editor.modified')}</span>}
        </div>
        <div className="editor-actions">
          <button className="btn" onClick={onCancel} disabled={saving}>
            {t('editor.cancel')}
          </button>
          <button
            className="btn btn--primary"
            onClick={handleSave}
            disabled={!hasChanges || saving}
          >
            {saving ? (
              <span>{t('editor.saving')}</span>
            ) : (
              <>
                <CheckIcon size={14} />
                <span>{t('editor.save')}</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="editor-body" data-color-mode="auto">
        <MDEditor
          value={content}
          onChange={(val) => setContent(val || '')}
          height="100%"
          preview="live"
          visibleDragbar
        />
      </div>

      <div className="editor-status">
        <span>{t('editor.pathLabel', { path: document.path })}</span>
        <span>{t('editor.sizeLabel', { size: (content.length / 1024).toFixed(1) })}</span>
        <span className="muted">{t('editor.shortcuts')}</span>
      </div>
    </div>
  )
}
