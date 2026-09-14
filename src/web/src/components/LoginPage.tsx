/**
 * 登录页(account-auth):未认证时整站门禁
 */
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { login } from '../api/client'
import { useToast } from './Toast'
import { AlertIcon } from './Icon'

export default function LoginPage() {
  const { t } = useTranslation()
  const toast = useToast()
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
      window.dispatchEvent(new CustomEvent('akm:session-changed'))
      toast.success(t('login.welcomeBack'))
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('login.failed')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login">
      <form className="login__card" onSubmit={handleSubmit}>
        <div className="login__brand">
          <h1>{t('layout.headerTitle')}</h1>
          <p>{t('login.welcome')}</p>
        </div>

        <div className="login__field">
          <label htmlFor="login-username">{t('login.username')}</label>
          <input
            id="login-username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            disabled={loading}
          />
        </div>

        <div className="login__field">
          <label htmlFor="login-password">{t('login.password')}</label>
          <input
            id="login-password"
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={loading}
          />
        </div>

        {error && (
          <div className="login__error" role="alert">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <AlertIcon size={14} /> <span>{error}</span>
            </span>
          </div>
        )}

        <button
          type="submit"
          className="btn btn--primary"
          disabled={loading || !username || !password}
        >
          {loading ? t('login.submitting') : t('login.submit')}
        </button>
      </form>
    </div>
  )
}
