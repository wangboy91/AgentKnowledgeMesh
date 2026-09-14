/**
 * 节点管理 · 表格 + 操作 + Token 一次性展示
 */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Node } from '../api/client'
import { useToast, useErrorReporter } from '../components/Toast'
import { formatRelative } from '../utils/format'
import {
  GlobeIcon,
  RefreshIcon,
  KeyIcon,
  TrashIcon,
  CopyIcon,
  BanIcon,
  CheckIcon,
} from '../components/Icon'

const platformMap: Record<string, string> = {
  darwin: 'macOS',
  windows: 'Windows',
  linux: 'Linux',
}

function platformIcon(platform: string): string {
  const map: Record<string, string> = { darwin: '🍎', windows: '🪟', linux: '🐧' }
  return map[platform] ?? '💻'
}

export default function Nodes() {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
  const [nodes, setNodes] = useState<Node[]>([])
  const [syncing, setSyncing] = useState<string | null>(null)
  const [newToken, setNewToken] = useState<{ id: string; token: string } | null>(null)
  const admin = isAdmin()

  useEffect(() => {
    loadNodes()
    const interval = setInterval(loadNodes, 10000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadNodes() {
    try {
      const data = await api.getNodes()
      setNodes(data)
    } catch (err) {
      reportError(err)
    }
  }

  async function handleSync(nodeId: string) {
    if (!admin) return
    setSyncing(nodeId)
    try {
      await api.syncNode(nodeId)
      toast.success(t('nodes.syncOk'))
      await loadNodes()
    } catch (err) {
      reportError(err)
    } finally {
      setSyncing(null)
    }
  }

  async function handleDelete(nodeId: string, nodeName: string) {
    if (!admin) return
    if (!confirm(t('nodes.confirmDelete', { name: nodeName }))) return
    try {
      await api.deleteNode(nodeId)
      toast.success(t('nodes.deleted', { name: nodeName }))
      await loadNodes()
    } catch (err) {
      reportError(err)
    }
  }

  async function handleResetToken(nodeId: string) {
    if (!admin) return
    if (!confirm(t('nodes.confirmResetToken'))) return
    try {
      const resp = await api.resetNodeToken(nodeId)
      setNewToken({ id: nodeId, token: resp.node_token })
      toast.warning(t('nodes.tokenSavedReminder'))
    } catch (err) {
      reportError(err)
    }
  }

  async function handleToggleDisabled(node: Node) {
    if (!admin) return
    const next = !node.disabled
    if (next && !confirm(t('nodes.confirmDisable'))) return
    try {
      await api.setNodeDisabled(node.id, next)
      toast.success(next ? t('nodes.disabled') : t('nodes.enabled'))
      await loadNodes()
    } catch (err) {
      reportError(err)
    }
  }

  async function copyToken() {
    if (!newToken) return
    try {
      await navigator.clipboard.writeText(newToken.token)
      toast.success(t('common.copied'))
    } catch {
      toast.warning(t('common.copyFailed'))
    }
  }

  return (
    <div className="page">
      <h2>{t('nodes.title')}</h2>
      <p className="page__desc">{t('nodes.subtitle')}</p>

      <div className="stats-grid">
        <div className="card">
          <span className="card__label">{t('nodes.total')}</span>
          <span className="card__value">{nodes.length}</span>
        </div>
        <div className="card">
          <span className="card__label">{t('nodes.online')}</span>
          <span className="card__value" style={{ color: 'var(--color-success)' }}>
            {nodes.filter((n) => n.status === 'online').length}
          </span>
        </div>
        <div className="card">
          <span className="card__label">{t('nodes.offline')}</span>
          <span className="card__value" style={{ color: 'var(--color-text-muted)' }}>
            {nodes.filter((n) => n.status === 'offline').length}
          </span>
        </div>
      </div>

      {newToken && (
        <div
          className="badge badge--warning"
          style={{
            display: 'block',
            padding: 'var(--space-3) var(--space-4)',
            marginBottom: 'var(--space-4)',
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <strong style={{ color: 'var(--color-text)', display: 'block', marginBottom: 4 }}>
            {t('nodes.newTokenSaved')}
          </strong>
          <div className="mono" style={{ wordBreak: 'break-all', color: 'var(--color-text)' }}>
            {newToken.token}
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
            <button className="btn btn--sm" onClick={copyToken}>
              <CopyIcon size={12} />
              <span>{t('common.copy')}</span>
            </button>
            <button className="btn btn--sm" onClick={() => setNewToken(null)}>
              {t('nodes.tokenSaved')}
            </button>
          </div>
        </div>
      )}

      {nodes.length === 0 ? (
        <div className="card" style={{ marginTop: 'var(--space-4)' }}>
          <div className="state">
            <div className="state__illustration">
              <GlobeIcon size={28} />
            </div>
            <div className="state__title">{t('nodes.noNodes')}</div>
            <div className="state__desc">{t('nodes.nodeHint')}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <code className="mono" style={{ background: 'var(--color-bg)', padding: 'var(--space-1) var(--space-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                  uv run akm-node login
                </code>
                <span className="state__cmd-hint">{t('nodes.firstLoginHint')}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <code className="mono" style={{ background: 'var(--color-bg)', padding: 'var(--space-1) var(--space-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
                  uv run akm-node
                </code>
                <span className="state__cmd-hint">{t('nodes.runHint')}</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table className="table">
            <thead>
              <tr>
                <th>{t('nodes.node')}</th>
                <th>{t('nodes.platform')}</th>
                <th>{t('nodes.status')}</th>
                <th>{t('nodes.lastHeartbeat')}</th>
                <th style={{ textAlign: 'right' }}>{t('nodes.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => (
                <tr key={node.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span style={{ fontSize: 16 }}>{platformIcon(node.platform)}</span>
                      <div>
                        <div style={{ fontWeight: 500 }}>{node.name}</div>
                        <div className="mono subtle" style={{ fontSize: 11 }}>{node.id}</div>
                      </div>
                    </div>
                  </td>
                  <td>{platformMap[node.platform] ?? node.platform}</td>
                  <td>
                    {node.disabled ? (
                      <span className="badge badge--muted">
                        <BanIcon size={12} />
                        <span>{t('nodes.disabledShort')}</span>
                      </span>
                    ) : node.status === 'online' ? (
                      <span className="badge badge--success">
                        <CheckIcon size={12} />
                        <span>{t('nodes.online')}</span>
                      </span>
                    ) : (
                      <span className="badge badge--muted">
                        <span>{t('nodes.offline')}</span>
                      </span>
                    )}
                  </td>
                  <td className="muted">{formatRelative(node.last_heartbeat)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {admin ? (
                      <div style={{ display: 'inline-flex', gap: 4 }}>
                        <button
                          className="icon-btn"
                          onClick={() => handleSync(node.id)}
                          disabled={syncing === node.id || node.status === 'offline'}
                          title={t('nodes.sync')}
                          aria-label={t('nodes.sync')}
                        >
                          <RefreshIcon size={14} />
                        </button>
                        <button
                          className="icon-btn"
                          onClick={() => handleResetToken(node.id)}
                          title={t('nodes.resetToken')}
                          aria-label={t('nodes.resetToken')}
                        >
                          <KeyIcon size={14} />
                        </button>
                        <button
                          className="icon-btn"
                          onClick={() => handleToggleDisabled(node)}
                          title={node.disabled ? t('nodes.enable') : t('nodes.disable')}
                          aria-label={node.disabled ? t('nodes.enable') : t('nodes.disable')}
                        >
                          <BanIcon size={14} />
                        </button>
                        <button
                          className="icon-btn"
                          onClick={() => handleDelete(node.id, node.name)}
                          title={t('nodes.deleteNode')}
                          aria-label={t('nodes.deleteNode')}
                          style={{ color: 'var(--color-danger)' }}
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    ) : (
                      <span className="muted" style={{ fontSize: 12 }}>{t('nodes.readOnly')}</span>
                    )}
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
