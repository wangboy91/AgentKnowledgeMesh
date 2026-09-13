import { useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import LoginPage from './components/LoginPage'
import Dashboard from './pages/Dashboard'
import Knowledge from './pages/Knowledge'
import Nodes from './pages/Nodes'
import Settings from './pages/Settings'
import { getSession } from './api/client'

function App() {
  // 登录门禁(account-auth):未登录或会话失效时展示登录页
  const [authenticated, setAuthenticated] = useState(() => !!getSession())

  useEffect(() => {
    const onUnauthorized = () => setAuthenticated(false)
    const onSessionChanged = () => setAuthenticated(!!getSession())
    window.addEventListener('akm:unauthorized', onUnauthorized)
    window.addEventListener('akm:session-changed', onSessionChanged)
    return () => {
      window.removeEventListener('akm:unauthorized', onUnauthorized)
      window.removeEventListener('akm:session-changed', onSessionChanged)
    }
  }, [])

  if (!authenticated) {
    return <LoginPage />
  }

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/*" element={<Knowledge />} />
        <Route path="nodes" element={<Nodes />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
