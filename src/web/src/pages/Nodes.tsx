import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Node } from '../api/client'

export default function Nodes() {
  const { t } = useTranslation()
  const [nodes, setNodes] = useState<Node[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [newToken, setNewToken] = useState<string | null>(null) // 重置后的节点 token(一次性展示)
  const admin = isAdmin()

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
    if (!confirm(t('nodes.confirmDelete'))) return

    try {
      await api.deleteNode(nodeId)
      await loadNodes()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('nodes.deleteFailed'))
    }
  }

  /** 重置节点 token(admin):旧 token 立即失效,新 token 仅此展示一次 */
  async function handleResetToken(nodeId: string) {
    if (!confirm(t('nodes.confirmResetToken'))) return
    setError('')
    try {
      const resp = await api.resetNodeToken(nodeId)
      setNewToken(resp.node_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('nodes.resetFailed'))
    }
  }

  /** 禁用/启用节点(admin) */
  async function handleToggleDisabled(node: Node) {
    const next = !node.disabled
    if (next && !confirm(t('nodes.confirmDisable'))) return
    setError('')
    try {
      await api.setNodeDisabled(node.id, next)
      await loadNodes()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('nodes.actionFailed'))
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
      <h2 style={{ marginBottom: '24px' }}>{t('nodes.title')}</h2>

      {error && (
        <div style={{ color: '#e5484d', fontSize: 13, marginBottom: 12 }}>{error}</div>
      )}

      {newToken && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            borderRadius: 8,
            border: '1px solid var(--accent)',
            fontSize: 13,
            wordBreak: 'break-all',
          }}
        >
          <strong>{t('nodes.newTokenSaved')}</strong>
          <div style={{ fontFamily: 'monospace', marginTop: 6 }}>{newToken}</div>
          <button style={{ marginTop: 8 }} onClick={() => setNewToken(null)}>
            {t('nodes.tokenSaved')}
          </button>
        </div>
      )}

      <div className="stats-grid" style={{ marginBottom: '32px' }}>
        <div className="stat-card">
          <h3>{nodes.length}</h3>
          <p>{t('nodes.total')}</p>
        </div>
        <div className="stat-card">
          <h3>{nodes.filter(n => n.status === 'online').length}</h3>
          <p>{t('nodes.online')}</p>
        </div>
        <div className="stat-card">
          <h3>{nodes.filter(n => n.status === 'offline').length}</h3>
          <p>{t('nodes.offline')}</p>
        </div>
      </div>

      {nodes.length === 0 ? (
        <div className="empty-state" style={{ minHeight: '300px' }}>
          <span style={{ fontSize: '48px' }}>🌐</span>
          <p>{t('nodes.noNodes')}</p>
          <div style={{ marginTop: '16px', color: 'var(--text-secondary)', textAlign: 'center' }}>
            <p>{t('nodes.nodeHint')}:</p>
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
                <th style={{ padding: '12px', textAlign: 'left' }}>{t('nodes.node')}</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>{t('nodes.platform')}</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>{t('nodes.status')}</th>
                <th style={{ padding: '12px', textAlign: 'left' }}>{t('nodes.lastHeartbeat')}</th>
                <th style={{ padding: '12px', textAlign: 'right' }}>{t('nodes.actions')}</th>
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
                      {node.status === 'online' ? `🟢 ${t('nodes.online')}` : `⚪ ${t('nodes.offline')}`}
                    </span>
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>
                    {formatTime(node.last_heartbeat)}
                  </td>
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    {admin && (
                      <>
                        <button
                          className="btn"
                          onClick={() => handleSync(node.id)}
                          disabled={syncing === node.id || node.status === 'offline'}
                          style={{ marginRight: '8px' }}
                        >
                          {syncing === node.id ? t('nodes.syncing') : t('nodes.sync')}
                        </button>
                        <button
                          className="btn"
                          onClick={() => handleResetToken(node.id)}
                          style={{ marginRight: '8px' }}
                        >
                          {t('nodes.resetToken')}
                        </button>
                        <button
                          className="btn"
                          onClick={() => handleToggleDisabled(node)}
                          style={{ marginRight: '8px', color: node.disabled ? 'var(--accent)' : 'var(--danger)' }}
                        >
                          {node.disabled ? t('nodes.enable') : t('nodes.disable')}
                        </button>
                        <button
                          className="btn"
                          onClick={() => handleDelete(node.id)}
                          style={{ color: 'var(--danger)' }}
                        >
                          {t('nodes.deleteNode')}
                        </button>
                      </>
                    )}
                    {!admin && <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{t('nodes.readOnly')}</span>}
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
