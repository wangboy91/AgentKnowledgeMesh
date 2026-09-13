import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, type ApiTokenInfo } from '../api/client'

/** 设置页:API Token 管理 + RAG 模式(admin) */
export default function Settings() {
  const { t } = useTranslation()
  const [tokens, setTokens] = useState<ApiTokenInfo[]>([])
  const [name, setName] = useState('')
  const [role, setRole] = useState<'admin' | 'viewer'>('viewer')
  const [plaintext, setPlaintext] = useState('') // 新建 token 的一次性明文
  const [ragMode, setRagModeState] = useState<'auto' | 'manual'>('auto')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const admin = isAdmin()

  const refresh = useCallback(async () => {
    try {
      setTokens(await api.getApiTokens())
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.loadFailed'))
    }
  }, [t])

  const refreshRagMode = useCallback(async () => {
    try {
      setRagModeState((await api.getSettings()).rag_sync_mode)
    } catch {
      /* 读取失败保持默认;开关操作会重试 */
    }
  }, [])

  useEffect(() => {
    if (admin) {
      refresh()
      refreshRagMode()
    }
  }, [admin, refresh, refreshRagMode])

  async function handleCreate() {
    if (!name.trim()) return
    setLoading(true)
    setError('')
    try {
      const created = await api.createApiToken(name.trim(), role)
      setPlaintext(created.token)
      setName('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.createFailed'))
    } finally {
      setLoading(false)
    }
  }

  async function handleRevoke(id: number) {
    if (!confirm(t('settings.revokeConfirm'))) return
    setError('')
    try {
      await api.revokeApiToken(id)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.revokeFailed'))
    }
  }

  async function handleRagMode(mode: 'auto' | 'manual') {
    if (mode === 'manual' && !confirm(t('settings.ragConfirmManual'))) return
    setError('')
    try {
      await api.setRagMode(mode)
      setRagModeState(mode)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.switchFailed'))
    }
  }

  if (!admin) {
    return <div className="page"><h2>{t('nav.settings')}</h2><p>{t('settings.adminOnly')}</p></div>
  }

  return (
    <div className="page" style={{ padding: 24, maxWidth: 860 }}>
      <h2>{t('settings.title')}</h2>
      <p style={{ color: 'var(--text-secondary, #888)', fontSize: 13 }}>
        {t('settings.desc')}
      </p>

      <div
        style={{
          padding: 16,
          margin: '16px 0 24px',
          borderRadius: 10,
          border: '1px solid var(--border-color, #ddd)',
          background: 'var(--bg-tertiary, #fafafa)',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8 }}>{t('settings.ragTitle')}</div>
        <div style={{ color: 'var(--text-secondary, #888)', fontSize: 13, marginBottom: 12 }}>
          {t('settings.ragDesc')}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => handleRagMode('auto')}
            disabled={ragMode === 'auto'}
            style={ragMode === 'auto' ? { opacity: 0.6 } : undefined}
          >
            {ragMode === 'auto' ? `✓ ${t('settings.ragAuto')}` : t('settings.ragAuto')}
          </button>
          <button
            onClick={() => handleRagMode('manual')}
            disabled={ragMode === 'manual'}
            style={ragMode === 'manual' ? { opacity: 0.6 } : undefined}
          >
            {ragMode === 'manual' ? `✓ ${t('settings.ragManual')}` : t('settings.ragManual')}
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, margin: '16px 0' }}>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder={t('settings.tokenNamePlaceholder')}
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border-color, #ddd)' }}
        />
        <select
          value={role}
          onChange={e => setRole(e.target.value as 'admin' | 'viewer')}
          style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border-color, #ddd)' }}
        >
          <option value="viewer">{t('settings.roleViewer')}</option>
          <option value="admin">{t('settings.roleAdmin')}</option>
        </select>
        <button onClick={handleCreate} disabled={loading || !name.trim()}>
          {t('settings.create')}
        </button>
      </div>

      {plaintext && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            borderRadius: 8,
            background: 'var(--accent-soft, #eef3ff)',
            border: '1px solid var(--accent-color, #4f7cff)',
            fontSize: 13,
            wordBreak: 'break-all',
          }}
        >
          <strong>{t('settings.saveOnce')}</strong>
          <div style={{ fontFamily: 'monospace', marginTop: 6 }}>{plaintext}</div>
          <button style={{ marginTop: 8 }} onClick={() => setPlaintext('')}>
            {t('settings.savedClose')}
          </button>
        </div>
      )}

      {error && <div style={{ color: '#e5484d', fontSize: 13, marginBottom: 12 }}>{error}</div>}

      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--text-secondary, #888)' }}>
            <th style={{ padding: 6 }}>{t('settings.nameCol')}</th>
            <th style={{ padding: 6 }}>{t('settings.prefixCol')}</th>
            <th style={{ padding: 6 }}>{t('settings.roleCol')}</th>
            <th style={{ padding: 6 }}>{t('settings.createdCol')}</th>
            <th style={{ padding: 6 }}>{t('settings.statusCol')}</th>
            <th style={{ padding: 6 }}></th>
          </tr>
        </thead>
        <tbody>
          {tokens.map(tr => (
            <tr key={tr.id} style={{ borderTop: '1px solid var(--border-color, #eee)' }}>
              <td style={{ padding: 6 }}>{tr.name}</td>
              <td style={{ padding: 6, fontFamily: 'monospace' }}>{tr.token_prefix}…</td>
              <td style={{ padding: 6 }}>{tr.role}</td>
              <td style={{ padding: 6 }}>{tr.created_at?.slice(0, 19).replace('T', ' ')}</td>
              <td style={{ padding: 6 }}>{tr.revoked ? t('settings.revoked') : t('settings.active')}</td>
              <td style={{ padding: 6 }}>
                {!tr.revoked && (
                  <button onClick={() => handleRevoke(tr.id)}>{t('settings.revoke')}</button>
                )}
              </td>
            </tr>
          ))}
          {tokens.length === 0 && (
            <tr>
              <td colSpan={6} style={{ padding: 12, color: 'var(--text-secondary, #888)' }}>
                {t('settings.noTokens')}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
