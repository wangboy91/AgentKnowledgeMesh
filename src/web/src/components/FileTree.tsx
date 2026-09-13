import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Document } from '../api/client'

interface TreeNode {
  [key: string]: TreeNode | { _title: string; _path: string; _rag_status?: string }
}

interface FileTreeProps {
  /** 当前选中的节点(树按节点过滤;null 全量) */
  selectedNodeId?: string | null
  /** 受控展开集合(目录路径) */
  expanded: string[]
  onToggleFolder: (path: string) => void
  /** 一次性设置展开集合(全部展开/收起用) */
  onSetExpanded: (dirs: string[]) => void
}

const RAG_STYLE: Record<string, { label: string; color: string }> = {
  indexed: { label: '✓', color: 'var(--accent, #4f7cff)' },
  pending: { label: '⏳', color: '#e5a00d' },
  excluded: { label: '⛔', color: 'var(--text-secondary, #888)' },
}

/** 收集树中全部目录路径(用于"全部展开") */
function collectAllDirs(node: TreeNode, prefix = ''): string[] {
  const dirs: string[] = []
  for (const [name, value] of Object.entries(node)) {
    if (name.startsWith('_')) continue
    if (!(value as any)._path) {
      const p = prefix ? `${prefix}/${name}` : name
      dirs.push(p)
      dirs.push(...collectAllDirs(value as TreeNode, p))
    }
  }
  return dirs
}

/** 文件树:按节点过滤、受控展开;文件项带 RAG 状态徽标与单篇/批量勾选(admin) */
export default function FileTree({
  selectedNodeId = null,
  expanded,
  onToggleFolder,
  onSetExpanded,
}: FileTreeProps) {
  const { t } = useTranslation()
  const [tree, setTree] = useState<TreeNode>({})
  const [docs, setDocs] = useState<Document[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const admin = isAdmin()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [t, d] = await Promise.all([
        api.getDocumentTree(selectedNodeId ?? undefined),
        api.getDocuments(selectedNodeId ?? undefined),
      ])
      setTree(t)
      setDocs(d)
    } catch (err) {
      console.error('Failed to load tree:', err)
    } finally {
      setLoading(false)
    }
  }, [selectedNodeId])

  useEffect(() => {
    load()
  }, [load])

  async function toggleRag(docPath: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!admin || busy) return
    const doc = docs.find((d) => d.path === docPath)
    if (!doc) return
    setBusy(true)
    try {
      await api.setDocumentRag(doc.id, doc.rag_status === 'excluded')
      await load()
    } finally {
      setBusy(false)
    }
  }

  async function batchSet(mode: 'add' | 'remove') {
    if (!admin || busy) return
    const target =
      mode === 'add'
        ? docs.filter((d) => d.rag_status === 'excluded').map((d) => d.id)
        : docs.filter((d) => d.rag_status !== 'excluded').map((d) => d.id)
    if (!target.length) return
    setBusy(true)
    try {
      await api.batchSetRag(target, mode === 'add')
      await load()
    } finally {
      setBusy(false)
    }
  }

  function toggleFolder(path: string) {
    onToggleFolder(path)
  }

  function renderNode(name: string, node: TreeNode | any, path = ''): React.ReactNode {
    const currentPath = path ? `${path}/${name}` : name

    if (node._path) {
      if (filter && (node._rag_status || '') !== filter) return null
      const style = RAG_STYLE[node._rag_status || 'indexed']
      return (
        <div
          key={node._path}
          className="tree-item tree-file-item"
          role="button"
          tabIndex={0}
          onClick={() => navigate(`/knowledge/${node._path}`)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') navigate(`/knowledge/${node._path}`)
          }}
        >
          <span className="tree-icon">📄</span>
          <span className="tree-label" style={{ flex: 1 }}>{node._title || name}</span>
          {admin && (
            <span
              className="tree-rag-badge"
              title={t('filetree.ragTitle', { status: node._rag_status || 'indexed' })}
              onClick={(e) => toggleRag(node._path, e)}
              style={{
                color: style.color,
                cursor: 'pointer',
                fontSize: 12,
                marginLeft: 6,
              }}
            >
              {style.label}
            </span>
          )}
        </div>
      )
    }

    const isExpanded = expanded.includes(currentPath)
    const children = Object.entries(node)
      .filter(([key]) => !key.startsWith('_'))
      .sort(([a, aNode], [b, bNode]) => {
        const aIsFolder = !(aNode as any)._path
        const bIsFolder = !(bNode as any)._path
        if (aIsFolder && !bIsFolder) return -1
        if (!aIsFolder && bIsFolder) return 1
        return a.localeCompare(b)
      })

    return (
      <div key={currentPath} className="tree-folder-container">
        <div
          className="tree-item tree-folder-item"
          role="button"
          tabIndex={0}
          onClick={() => toggleFolder(currentPath)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              toggleFolder(currentPath)
            }
          }}
        >
          <span className="tree-arrow">{isExpanded ? '▼' : '▶'}</span>
          <span className="tree-icon">{isExpanded ? '📂' : '📁'}</span>
          <span className="tree-label">{name}</span>
        </div>
        {isExpanded && (
          <div className="tree-children">
            {children.map(([childName, childNode]) => renderNode(childName, childNode, currentPath))}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return <div className="file-tree loading">Loading...</div>
  }

  if (Object.keys(tree).length === 0) {
    return (
      <div className="file-tree empty-state">
        <p>{t('filetree.noDocuments')}</p>
        <button className="btn" onClick={() => api.scanDocuments().then(load)}>
          {t('filetree.scanNow')}
        </button>
      </div>
    )
  }

  return (
    <div className="file-tree">
      <div style={{ display: 'flex', gap: 6, padding: '6px 0', borderBottom: '1px solid var(--border-color)', alignItems: 'center' }}>
        <button style={{ fontSize: 12, padding: '2px 6px' }} onClick={() => onSetExpanded(collectAllDirs(tree))} title={t('filetree.expandAll')}>
          {t('filetree.expandAll')}
        </button>
        <button style={{ fontSize: 12, padding: '2px 6px' }} onClick={() => onSetExpanded([])} title={t('filetree.collapseAll')}>
          {t('filetree.collapseAll')}
        </button>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ flex: 1, fontSize: 12, padding: '2px 4px' }}
        >
          <option value="">{t('filetree.allStatus')}</option>
          <option value="indexed">✓ indexed</option>
          <option value="pending">⏳ pending</option>
          <option value="excluded">⛔ excluded</option>
        </select>
        {admin && (
          <>
            <button style={{ fontSize: 12, padding: '2px 6px' }} onClick={() => batchSet('add')} disabled={busy}>
              {t('filetree.ragAdd')}
            </button>
            <button style={{ fontSize: 12, padding: '2px 6px' }} onClick={() => batchSet('remove')} disabled={busy}>
              {t('filetree.ragRemove')}
            </button>
          </>
        )}
      </div>
      {Object.entries(tree).map(([name, node]) => renderNode(name, node))}
    </div>
  )
}