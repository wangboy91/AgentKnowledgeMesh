import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { login } from '../api/client'

/** 登录页(account-auth):未认证时整站门禁 */
export default function LoginPage() {
  const { t } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      // 登录成功后整站刷新状态(由 App 层监听会话变化)
      window.dispatchEvent(new CustomEvent('akm:session-changed'))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('login.failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-color, #f5f6f8)',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: 320,
          padding: 32,
          borderRadius: 12,
          border: '1px solid var(--border-color, #e0e0e0)',
          background: 'var(--panel-bg, #fff)',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <h1 style={{ fontSize: 20, margin: 0, textAlign: 'center' }}>
          🔐 AgentKnowledgeMesh
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary, #888)', textAlign: 'center', margin: 0 }}>
          {t('login.welcome')}
        </p>
        <input
          value={username}
          onChange={e => setUsername(e.target.value)}
          placeholder={t('login.username')}
          autoFocus
          style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-color, #ddd)' }}
        />
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder={t('login.password')}
          style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-color, #ddd)' }}
        />
        {error && <div style={{ color: '#e5484d', fontSize: 13 }}>{error}</div>}
        <button
          type="submit"
          disabled={loading || !username || !password}
          style={{
            padding: '10px 12px',
            borderRadius: 8,
            border: 'none',
            background: 'var(--accent-color, #4f7cff)',
            color: '#fff',
            cursor: loading ? 'wait' : 'pointer',
            fontWeight: 600,
          }}
        >
          {loading ? t('login.submitting') : t('login.submit')}
        </button>
      </form>
    </div>
  )
}
