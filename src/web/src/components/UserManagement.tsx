/**
 * 用户管理 · 创建账号 / 分配角色 / 重置密码 / 停用启用 / 删除
 *
 * 与后端 /api/auth/users 对应;安全约束(与后端一致):
 * - 不能删除当前登录账号
 * - 不能停用/降级最后一个可用管理员
 */
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, getSession, type UserInfo } from '../api/client'
import { useToast, useErrorReporter } from './Toast'
import {
  PlusIcon,
  TrashIcon,
  BanIcon,
  CheckIcon,
  KeyIcon,
  XIcon,
} from './Icon'
import { formatDate } from '../utils/format'

export default function UserManagement() {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
  const me = getSession()

  const [users, setUsers] = useState<UserInfo[]>([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'admin' | 'viewer'>('viewer')
  const [busy, setBusy] = useState(false)

  // 行内重置密码
  const [resettingId, setResettingId] = useState<number | null>(null)
  const [newPassword, setNewPassword] = useState('')

  const refresh = useCallback(async () => {
    try {
      setUsers(await api.getUsers())
    } catch (err) {
      reportError(err)
    }
  }, [reportError])

  useEffect(() => {
    refresh()
  }, [refresh])

  // 最后一个可用管理员:禁止停用/降级,避免把自己锁在门外
  const enabledAdmins = users.filter((u) => u.role === 'admin' && !u.disabled)
  const isLastAdmin = (u: UserInfo) =>
    enabledAdmins.length === 1 && enabledAdmins[0].id === u.id
  const isSelf = (u: UserInfo) => u.username === me?.username

  async function handleCreate() {
    if (!username.trim() || !password || busy) return
    setBusy(true)
    try {
      await api.createUser(username.trim(), password, role)
      setUsername('')
      setPassword('')
      setRole('viewer')
      toast.success(t('settings.userCreated'))
      await refresh()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleToggleDisabled(u: UserInfo) {
    if (busy) return
    if (!u.disabled && isLastAdmin(u)) return
    setBusy(true)
    try {
      await api.updateUser(u.id, { disabled: !u.disabled })
      toast.success(t('settings.userUpdated'))
      await refresh()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleRole(u: UserInfo, next: 'admin' | 'viewer') {
    if (busy || next === u.role) return
    if (next === 'viewer' && isLastAdmin(u)) return
    setBusy(true)
    try {
      await api.updateUser(u.id, { role: next })
      toast.success(t('settings.userUpdated'))
      await refresh()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleResetPassword(u: UserInfo) {
    if (!newPassword || busy) return
    setBusy(true)
    try {
      await api.updateUser(u.id, { password: newPassword })
      toast.success(t('settings.passwordReset'))
      setResettingId(null)
      setNewPassword('')
      await refresh()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(u: UserInfo) {
    if (busy) return
    if (isSelf(u)) {
      toast.warning(t('settings.cannotDeleteSelf'))
      return
    }
    if (!confirm(t('settings.deleteUserConfirm', { name: u.username }))) return
    setBusy(true)
    try {
      await api.deleteUser(u.id)
      toast.success(t('settings.userDeleted'))
      await refresh()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="settings-section" style={{ padding: 0 }}>
      <div style={{ padding: 'var(--space-5)' }}>
        <h3>{t('settings.usersTitle')}</h3>
        <p style={{ marginBottom: 'var(--space-3)' }}>{t('settings.usersDesc')}</p>

        {/* 创建用户 */}
        <div className="settings-row">
          <input
            className="input"
            style={{ flex: '1 1 180px', minWidth: 160 }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t('settings.usernamePlaceholder')}
            aria-label={t('settings.usernamePlaceholder')}
          />
          <input
            className="input"
            type="password"
            style={{ flex: '1 1 180px', minWidth: 160 }}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('settings.passwordPlaceholder')}
            aria-label={t('settings.passwordPlaceholder')}
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
            disabled={busy || !username.trim() || !password}
          >
            <PlusIcon size={14} />
            <span>{t('settings.createUser')}</span>
          </button>
        </div>
      </div>

      {users.length === 0 ? (
        <div className="table__empty">{t('settings.noUsers')}</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t('settings.usernameCol')}</th>
              <th>{t('settings.roleCol')}</th>
              <th>{t('settings.statusCol')}</th>
              <th>{t('settings.createdCol')}</th>
              <th style={{ textAlign: 'right' }}>{t('nodes.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <strong>{u.username}</strong>
                  {isSelf(u) && (
                    <span className="badge badge--muted" style={{ marginLeft: 6 }}>
                      {t('settings.youLabel')}
                    </span>
                  )}
                </td>
                <td>
                  <select
                    className="select"
                    style={{ height: 28, fontSize: 'var(--text-xs-size)' }}
                    value={u.role}
                    onChange={(e) => handleRole(u, e.target.value as 'admin' | 'viewer')}
                    disabled={busy || isLastAdmin(u)}
                    title={isLastAdmin(u) ? t('settings.lastAdminHint') : undefined}
                  >
                    <option value="viewer">{t('settings.roleViewer')}</option>
                    <option value="admin">{t('settings.roleAdmin')}</option>
                  </select>
                </td>
                <td>
                  {u.disabled ? (
                    <span className="badge badge--danger">{t('settings.statusDisabled')}</span>
                  ) : (
                    <span className="badge badge--success">{t('settings.statusEnabled')}</span>
                  )}
                </td>
                <td className="muted">{formatDate(u.created_at, '—')}</td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {resettingId === u.id ? (
                    <span className="row" style={{ justifyContent: 'flex-end' }}>
                      <input
                        className="input"
                        type="password"
                        autoFocus
                        style={{ width: 140, height: 28 }}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleResetPassword(u)
                          if (e.key === 'Escape') {
                            setResettingId(null)
                            setNewPassword('')
                          }
                        }}
                        placeholder={t('settings.newPasswordPlaceholder')}
                        aria-label={t('settings.newPasswordPlaceholder')}
                      />
                      <button
                        className="icon-btn"
                        style={{ color: 'var(--color-success)' }}
                        onClick={() => handleResetPassword(u)}
                        disabled={busy || !newPassword}
                        title={t('settings.savePassword')}
                        aria-label={t('settings.savePassword')}
                      >
                        <CheckIcon size={14} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => {
                          setResettingId(null)
                          setNewPassword('')
                        }}
                        title={t('common.cancel')}
                        aria-label={t('common.cancel')}
                      >
                        <XIcon size={14} />
                      </button>
                    </span>
                  ) : (
                    <>
                      <button
                        className="icon-btn"
                        onClick={() => {
                          setResettingId(u.id)
                          setNewPassword('')
                        }}
                        title={t('settings.resetPassword')}
                        aria-label={t('settings.resetPassword')}
                      >
                        <KeyIcon size={14} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => handleToggleDisabled(u)}
                        disabled={busy || (!u.disabled && isLastAdmin(u))}
                        title={u.disabled ? t('settings.enable') : t('settings.disable')}
                        aria-label={u.disabled ? t('settings.enable') : t('settings.disable')}
                      >
                        {u.disabled ? <CheckIcon size={14} /> : <BanIcon size={14} />}
                      </button>
                      <button
                        className="icon-btn"
                        style={{ color: 'var(--color-danger)' }}
                        onClick={() => handleDelete(u)}
                        disabled={busy || isSelf(u)}
                        title={isSelf(u) ? t('settings.cannotDeleteSelf') : t('settings.deleteUser')}
                        aria-label={t('settings.deleteUser')}
                      >
                        <TrashIcon size={14} />
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
