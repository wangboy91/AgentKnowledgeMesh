import { useState, useEffect } from 'react'
import { api, Node } from '../api/client'

export default function Nodes() {
  const [nodes, setNodes] = useState<Node[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<string | null>(null)

  useEffect(() => {
    loadNodes()
    const interval = setInterval(loadNodes, 10000)
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

  async function handleSync(nodeId: string) {
    setSyncing(nodeId)
    try {
      await api.syncNode(nodeId)
      await loadNodes()
    } catch (err) {
      console.error('Sync failed:', err)
    } finally {
      setSyncing(null)
    }
  }

  async function handleDelete(nodeId: string) {
    if (!confirm('Delete this node and all its documents?')) return

    try {
      await api.deleteNode(nodeId)
      await loadNodes()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  function getPlatformIcon(platform: string) {
    switch (platform) {
      case 'darwin': return '🍎 macOS'
      case 'windows': return '🪟 Windows'
      case 'linux': return '🐧 Linux'
      default: return '💻 Unknown'
    }
  }

  function formatTime(iso: string | null) {
    if (!iso) return 'Never'
    return new Date(iso).toLocaleString()
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  return (
    <div className="dashboard">
      <h2 style={{ marginBottom: '24px' }}>Node Management</h2>

      <div className="stats-grid" style={{ marginBottom: '32px' }}>
        <div className="stat-card">
          <h3>{nodes.length}</h3>
          <p>Total Nodes</p>
        </div>
        <div className="stat-card">
          <h3>{nodes.filter(n => n.status === 'online').length}</h3>
          <p>Online</p>
        </div>
        <div className="stat-card">
          <h3>{nodes.filter(n => n.status === 'offline').length}</h3>
          <p>Offline</p>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="empty-state" style={{ minHeight: '300px' }}>
          <span style={{ fontSize: '48px' }}>🌐</span>
          <p>No nodes connected</p>
          <div style={{ marginTop: '16px', color: 'var(--text-secondary)', textAlign: 'center' }}>
            <p>Run the node client on another machine:</p>
            <code style={{
              display: 'block',
              marginTop: '8px',
              padding: '12px',
              background: 'var(--bg-tertiary)',
              borderRadius: '6px',
            }}>
              cd node && python main.py
            </code>
          </div>
        </div>
      ) : (
        <div className="nodes-table">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '12px', textAlign: 'left' }}>Node</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Platform</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>Last Heartbeat</th>
                <th style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => (
                <tr key={node.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px' }}>
                    <div style={{ fontWeight: 500 }}>{node.name}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{node.id}</div>
                  </td>
                  <td style={{ padding: '12px' }}>{getPlatformIcon(node.platform)}</td>
                  <td style={{ padding: '12px' }}>
                    <span className={`node-status-badge ${node.status}`}>
                      {node.status === 'online' ? '🟢 Online' : '⚪ Offline'}
                    </span>
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>
                    {formatTime(node.last_heartbeat)}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    <button
                      className="btn"
                      onClick={() => handleSync(node.id)}
                      disabled={syncing === node.id || node.status === 'offline'}
                      style={{ marginRight: '8px' }}
                    >
                      {syncing === node.id ? 'Syncing...' : '🔄 Sync'}
                    </button>
                    <button
                      className="btn"
                      onClick={() => handleDelete(node.id)}
                      style={{ color: 'var(--danger)' }}
                    >
                      🗑️ Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
