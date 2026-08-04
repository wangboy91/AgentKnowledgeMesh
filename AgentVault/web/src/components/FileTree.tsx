import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Document } from '../api/client'

interface TreeNode {
  [key: string]: TreeNode | { _title: string; _path: string }
}

export default function FileTree() {
  const [tree, setTree] = useState<TreeNode>({})
  const [loading, setLoading] = useState(true)
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

  function renderNode(name: string, node: TreeNode | any, path = ''): React.ReactNode {
    const currentPath = path ? `${path}/${name}` : name

    if (node._path) {
      // 文件节点
      return (
        <div
          key={node._path}
          className="tree-item"
          onClick={() => navigate(`/knowledge/${node._path}`)}
        >
          <span className="tree-file">📄</span>
          <span>{node._title || name}</span>
        </div>
      )
    }

    // 文件夹节点
    const children = Object.entries(node)
      .filter(([key]) => !key.startsWith('_'))
      .sort(([a], [b]) => a.localeCompare(b))

    return (
      <div key={currentPath}>
        <div className="tree-item">
          <span className="tree-folder">📁</span>
          <span>{name}</span>
        </div>
        <div style={{ paddingLeft: '16px' }}>
          {children.map(([childName, childNode]) =>
            renderNode(childName, childNode, currentPath)
          )}
        </div>
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
