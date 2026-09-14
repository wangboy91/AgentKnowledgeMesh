/**
 * 设置页 · RAG 同步模式 + API Token 管理
 */
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, type ApiTokenInfo } from '../api/client'
import { useToast, useErrorReporter } from '../components/Toast'
import UserManagement from '../components/UserManagement'
import {
  KeyIcon,
  CopyIcon,
  TrashIcon,
  AlertIcon,
  CheckIcon,
  BanIcon,
  RefreshIcon,
} from '../components/Icon'
import { formatDate } from '../utils/format'

/** 一次性展示的密钥(创建 / 轮换都会产生) */
interface IssuedSecret {
  secret: string
  name: string
  action: 'create' | 'rotate'
}

export default function Settings() {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
  const [tokens, setTokens] = useState<ApiTokenInfo[]>([])
  const [name, setName] = useState('')
  const [role, setRole] = useState<'admin' | 'viewer'>('viewer')
  const [issued, setIssued] = useState<IssuedSecret | null>(null)
  const [ragMode, setRagModeState] = useState<'auto' | 'manual'>('auto')
  const [showRevoked, setShowRevoked] = useState(false)
  const admin = isAdmin()

  // 吊销是软删除(保留记录以便审计),默认只展示有效 token
  const revokedTokens = tokens.filter((tr) => tr.revoked)
  const activeTokens = tokens.filter((tr) => !tr.revoked)
  const visibleTokens = showRevoked ? tokens : activeTokens

  const refresh = useCallback(async () => {
    try {
      setTokens(await api.getApiTokens())
    } catch (err) {
      reportError(err)
    }
  }, [reportError])

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
    if (!admin || !name.trim()) return
    try {
      const created = await api.createApiToken(name.trim(), role)
      setIssued({ secret: created.token, name: created.name, action: 'create' })
      setName('')
      toast.success(t('settings.created'))
      await refresh()
    } catch (err) {
      reportError(err)
    }
  }

  async function handleRotate(token: ApiTokenInfo) {
    if (!admin) return
    if (!confirm(t('settings.rotateConfirm', { name: token.name }))) return
    try {
      const rotated = await api.rotateApiToken(token.id)
      setIssued({ secret: rotated.token, name: rotated.name, action: 'rotate' })
      toast.success(t('settings.rotatedToast'))
      await refresh()
    } catch (err) {
      reportError(err)
    }
  }

  async function handleRevoke(token: ApiTokenInfo) {
    if (!admin) return
    if (!confirm(t('settings.revokeConfirm', { name: token.name }))) return
    try {
      await api.revokeApiToken(token.id)
      toast.success(t('settings.revokedToast'))
      await refresh()
    } catch (err) {
      reportError(err)
    }
  }

  async function handlePurge(token: ApiTokenInfo) {
    if (!admin) return
    if (!confirm(t('settings.purgeConfirm', { name: token.name }))) return
    try {
      await api.purgeApiToken(token.id)
      toast.success(t('settings.purgedToast'))
      await refresh()
    } catch (err) {
      reportError(err)
    }
  }

  async function handleRagMode(mode: 'auto' | 'manual') {
    if (!admin) return
    if (mode === 'manual' && !confirm(t('settings.ragConfirmManual'))) return
    try {
      await api.setRagMode(mode)
      setRagModeState(mode)
      toast.success(t('settings.switchedTo', { mode: t(`settings.rag${mode === 'auto' ? 'Auto' : 'Manual'}`) }))
    } catch (err) {
      reportError(err)
    }
  }

  async function copyPlaintext() {
    if (!issued) return
    try {
      await navigator.clipboard.writeText(issued.secret)
      toast.success(t('common.copied'))
    } catch {
      toast.warning(t('common.copyFailed'))
    }
  }

  if (!admin) {
    return (
      <div className="page">
        <h2>{t('nav.settings')}</h2>
        <div className="card" style={{ marginTop: 'var(--space-3)' }}>
          <p className="muted">{t('settings.adminOnly')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <h2>{t('settings.title')}</h2>
      <p className="page__desc">{t('settings.desc')}</p>

      {/* 用户管理 */}
      <UserManagement />

      {/* RAG Mode */}
      <section className="settings-section">
        <h3>{t('settings.ragTitle')}</h3>
        <p>{t('settings.ragDesc')}</p>
        <div className="settings-row">
          <button
            className={`btn ${ragMode === 'auto' ? 'btn--primary' : ''}`}
            onClick={() => handleRagMode('auto')}
            disabled={ragMode === 'auto'}
          >
            {ragMode === 'auto' && <CheckIcon size={14} />}
            <span>{t('settings.ragAuto')}</span>
          </button>
          <button
            className={`btn ${ragMode === 'manual' ? 'btn--primary' : ''}`}
            onClick={() => handleRagMode('manual')}
            disabled={ragMode === 'manual'}
          >
            {ragMode === 'manual' && <CheckIcon size={14} />}
            <span>{t('settings.ragManual')}</span>
          </button>
        </div>
      </section>

      {/* Token Create */}
      <section className="settings-section">
        <h3>{t('settings.tokenCreate')}</h3>
        <p>{t('settings.tokenCreateDesc')}</p>
        <div className="settings-row">
          <input
            className="input"
            style={{ flex: '1 1 240px', minWidth: 200 }}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('settings.tokenNamePlaceholder')}
            aria-label={t('settings.tokenNamePlaceholder')}
          />
          <select
            className="select"
            value={role}
            onChange={(e) => setRole(e.target.value as 'admin' | 'viewer')}
            aria-label={t('settings.roleLabel')}
          >
            <option value="viewer">{t('settings.roleViewer')}</option>
            <option value="admin">{t('settings.roleAdmin')}</option>
          </select>
          <button
            className="btn btn--primary"
            onClick={handleCreate}
            disabled={!name.trim()}
          >
            <KeyIcon size={14} />
            <span>{t('settings.create')}</span>
          </button>
        </div>

        {issued && (
          <div
            style={{
              marginTop: 'var(--space-3)',
              padding: 'var(--space-3)',
              background: 'var(--color-accent-soft)',
              border: '1px solid var(--color-accent)',
              borderRadius: 'var(--radius-lg)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--space-2)' }}>
              <AlertIcon size={16} />
              <strong>
                {issued.action === 'rotate'
                  ? t('settings.saveOnceRotated')
                  : t('settings.saveOnce')}
              </strong>
              <span className="muted">
                {t('settings.issuedFor', { name: issued.name })}
              </span>
            </div>
            <code
              className="mono"
              style={{
                display: 'block',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--color-bg)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                wordBreak: 'break-all',
                fontSize: 13,
              }}
            >
              {issued.secret}
            </code>
            {issued.action === 'rotate' && (
              <p className="muted" style={{ margin: 'var(--space-2) 0 0' }}>
                {t('settings.rotateHint')}
              </p>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
              <button className="btn btn--sm" onClick={copyPlaintext}>
                <CopyIcon size={12} />
                <span>{t('common.copy')}</span>
              </button>
              <button className="btn btn--sm" onClick={() => setIssued(null)}>
                {t('settings.savedClose')}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Token List */}
      <section className="settings-section" style={{ padding: 0 }}>
        <div
          style={{
            padding: 'var(--space-5)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 'var(--space-3)',
          }}
        >
          <div>
            <h3>{t('settings.tokenList')}</h3>
            <p style={{ marginBottom: 0 }}>{t('settings.tokenListDesc')}</p>
          </div>
          {revokedTokens.length > 0 && (
            <button
              className="btn btn--sm btn--ghost"
              onClick={() => setShowRevoked((v) => !v)}
              aria-pressed={showRevoked}
            >
              {showRevoked
                ? t('settings.hideRevoked')
                : t('settings.showRevoked', { count: revokedTokens.length })}
            </button>
          )}
        </div>
        {visibleTokens.length === 0 ? (
          <div className="table__empty">
            {revokedTokens.length > 0
              ? t('settings.noActiveTokens')
              : t('settings.noTokens')}
          </div>
        ) : (
          <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t('settings.nameCol')}</th>
                <th>{t('settings.prefixCol')}</th>
                <th>{t('settings.roleCol')}</th>
                <th>{t('settings.createdCol')}</th>
                <th>{t('settings.statusCol')}</th>
                <th style={{ textAlign: 'right' }}>{t('nodes.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {visibleTokens.map((tr) => (
                <tr key={tr.id}>
                  <td><strong>{tr.name}</strong></td>
                  <td><span className="table__mono">{tr.token_prefix}…</span></td>
                  <td>
                    <span className={`badge ${tr.role === 'admin' ? 'badge--accent' : 'badge--muted'}`}>
                      {tr.role}
                    </span>
                  </td>
                  <td className="muted">{formatDate(tr.created_at, '—')}</td>
                  <td>
                    {tr.revoked ? (
                      <span className="badge badge--danger">{t('settings.revoked')}</span>
                    ) : (
                      <span className="badge badge--success">{t('settings.active')}</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span className="row" style={{ justifyContent: 'flex-end' }}>
                      {!tr.revoked ? (
                        <>
                          <button
                            className="icon-btn"
                            onClick={() => handleRotate(tr)}
                            title={t('settings.rotate')}
                            aria-label={t('settings.rotate')}
                          >
                            <RefreshIcon size={14} />
                          </button>
                          <button
                            className="icon-btn"
                            style={{ color: 'var(--color-danger)' }}
                            onClick={() => handleRevoke(tr)}
                            title={t('settings.revoke')}
                            aria-label={t('settings.revoke')}
                          >
                            <BanIcon size={14} />
                          </button>
                        </>
                      ) : (
                        <button
                          className="icon-btn"
                          style={{ color: 'var(--color-danger)' }}
                          onClick={() => handlePurge(tr)}
                          title={t('settings.purge')}
                          aria-label={t('settings.purge')}
                        >
                          <TrashIcon size={14} />
                        </button>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>
    </div>
  )
}
