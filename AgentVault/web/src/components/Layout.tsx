import { Outlet, Link, useLocation } from 'react-router-dom'
import FileTree from './FileTree'
import SearchBar from './SearchBar'

export default function Layout() {
  const location = useLocation()
  const isKnowledge = location.pathname.startsWith('/knowledge')

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>🔐 AgentVault</h1>
          <p>Distributed Knowledge OS</p>
        </div>

        <nav style={{ padding: '12px 8px', borderBottom: '1px solid var(--border-color)' }}>
          <Link
            to="/"
            style={{
              display: 'block',
              padding: '8px 12px',
              color: location.pathname === '/' ? 'var(--bg-primary)' : 'var(--text-primary)',
              background: location.pathname === '/' ? 'var(--accent)' : 'transparent',
              borderRadius: '4px',
              textDecoration: 'none',
              marginBottom: '4px',
            }}
          >
            📊 Dashboard
          </Link>
          <Link
            to="/knowledge"
            style={{
              display: 'block',
              padding: '8px 12px',
              color: isKnowledge ? 'var(--bg-primary)' : 'var(--text-primary)',
              background: isKnowledge ? 'var(--accent)' : 'transparent',
              borderRadius: '4px',
              textDecoration: 'none',
            }}
          >
            📚 Knowledge
          </Link>
        </nav>

        {isKnowledge && <FileTree />}
      </aside>

      <main className="main-content">
        {isKnowledge && <SearchBar />}
        <Outlet />
      </main>
    </div>
  )
}
