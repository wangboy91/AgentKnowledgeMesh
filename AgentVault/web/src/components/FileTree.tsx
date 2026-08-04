import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

interface TreeNode {
  [key: string]: TreeNode | { _title: string; _path: string }
}

export default function FileTree() {
  const [tree, setTree] = useState<TreeNode>({})
  const [loading, setLoading] = useState(true)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const navigate = useNavigate()

  useEffect(() => {
    loadTree()
  }, [])

  async function loadTree() {
    try {
      const data = await api.getDocumentTree()
      setTree(data)
    } catch (err) {
      console.error('Failed to load tree:', err)
    } finally {
      setLoading(false)
    }
  }

  function toggleFolder(path: string) {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  function renderNode(name: string, node: TreeNode | any, path = ''): React.ReactNode {
    const currentPath = path ? `${path}/${name}` : name

    if (node._path) {
      // 文件节点
      return (
        <div
          key={node._path}
          className="tree-item tree-file-item"
          onClick={() => navigate(`/knowledge/${node._path}`)}
        >
          <span className="tree-icon">📄</span>
          <span className="tree-label">{node._title || name}</span>
        </div>
      )
    }

    // 文件夹节点
    const isExpanded = expandedFolders.has(currentPath)
    const children = Object.entries(node)
      .filter(([key]) => !key.startsWith('_'))
      .sort(([a, aNode], [b, bNode]) => {
        // 文件夹排在文件前面
        const aIsFolder = !aNode._path
        const bIsFolder = !bNode._path
        if (aIsFolder && !bIsFolder) return -1
        if (!aIsFolder && bIsFolder) return 1
        return a.localeCompare(b)
      })

    return (
      <div key={currentPath} className="tree-folder-container">
        <div className="tree-item tree-folder-item" onClick={() => toggleFolder(currentPath)}>
          <span className="tree-arrow">{isExpanded ? '▼' : '▶'}</span>
          <span className="tree-icon">{isExpanded ? '📂' : '📁'}</span>
          <span className="tree-label">{name}</span>
        </div>
        {isExpanded && (
          <div className="tree-children">
            {children.map(([childName, childNode]) =>
              renderNode(childName, childNode, currentPath)
            )}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return <div className="file-tree loading">Loading...</div>
  }

  const entries = Object.entries(tree)

  if (entries.length === 0) {
    return (
      <div className="file-tree empty-state">
        <p>No documents found</p>
        <button className="btn" onClick={() => api.scanDocuments().then(loadTree)}>
          Scan Now
        </button>
      </div>
    )
  }

  return (
    <div className="file-tree">
      {entries.map(([name, node]) => renderNode(name, node))}
    </div>
  )
}
