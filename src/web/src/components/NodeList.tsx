import { useState, useEffect } from 'react'
import { api, Node } from '../api/client'

interface Props {
  onSelectNode?: (nodeId: string | null) => void
  selectedNodeId?: string | null
}

export default function NodeList({ onSelectNode, selectedNodeId }: Props) {
  const [nodes, setNodes] = useState<Node[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadNodes()
    const interval = setInterval(loadNodes, 10000) // 每10秒刷新
    return () => clearInterval(interval)
  }, [])

  async function loadNodes() {
    try {
      const data = await api.getNodes()
      setNodes(data)
    } catch (err) {
      console.error('Failed to load nodes:', err)
    } finally {
      setLoading(false)
    }
  }

  function getPlatformIcon(platform: string) {
    switch (platform) {
      case 'darwin': return '🍎'
      case 'windows': return '🪟'
      case 'linux': return '🐧'
      default: return '💻'
    }
  }

  if (loading) {
    return <div className="loading">Loading nodes...</div>
  }

  return (
    <div className="node-list">
      <div
        className={`node-item ${selectedNodeId === null ? 'active' : ''}`}
        onClick={() => onSelectNode?.(null)}
      >
        <span className="node-icon">🏠</span>
        <span className="node-name">Local</span>
        <span className="node-status online">●</span>
      </div>

      {nodes.map((node) => (
        <div
          key={node.id}
          className={`node-item ${selectedNodeId === node.id ? 'active' : ''}`}
          onClick={() => onSelectNode?.(node.id)}
        >
          <span className="node-icon">{getPlatformIcon(node.platform)}</span>
          <span className="node-name">{node.name}</span>
          <span className={`node-status ${node.status}`}>
            {node.status === 'online' ? '●' : '○'}
          </span>
        </div>
      ))}

      {nodes.length === 0 && (
        <div className="node-empty">
          <p>No remote nodes</p>
          <p className="node-hint">Run node client to connect</p>
        </div>
      )}
    </div>
  )
}
