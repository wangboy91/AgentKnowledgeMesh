import { useState, useCallback } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { useTheme } from '../ThemeContext'
import FileTree from './FileTree'
import NodeList from './NodeList'
import SearchBar from './SearchBar'
import ResizeHandle from './ResizeHandle'

const DEFAULT_SIDEBAR_WIDTH = 280
const MIN_SIDEBAR_WIDTH = 200
const MAX_SIDEBAR_WIDTH = 500

export default function Layout() {
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  const isKnowledge = location.pathname.startsWith('/knowledge')
  const isNodes = location.pathname.startsWith('/nodes')

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('agentvault-sidebar-width')
    return saved ? parseInt(saved, 10) : DEFAULT_SIDEBAR_WIDTH
  })

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const handleResize = useCallback((width: number) => {
    setSidebarWidth(width)
    localStorage.setItem('agentvault-sidebar-width', width.toString())
  }, [])

  return (
    <div className="app-layout">
      <aside className="sidebar" style={{ width: sidebarWidth }}>
        <div className="sidebar-header">
          <div className="sidebar-header-left">
            <h1>🔐 AgentKnowledgeMesh</h1>
            <p>Distributed Knowledge OS</p>
          </div>
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>

        <nav style={{ padding: '12px 8px', borderBottom: '1px solid var(--border-color)' }}>
          <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
            📊 Dashboard
          </Link>
          <Link to="/knowledge" className={`nav-link ${isKnowledge ? 'active' : ''}`}>
            📚 Knowledge
          </Link>
          <Link to="/nodes" className={`nav-link ${isNodes ? 'active' : ''}`}>
            🌐 Nodes
          </Link>
        </nav>

        {isKnowledge && (
          <>
            <div style={{ padding: '8px', borderBottom: '1px solid var(--border-color)' }}>
              <NodeList onSelectNode={setSelectedNodeId} selectedNodeId={selectedNodeId} />
            </div>
            <FileTree />
          </>
        )}
      </aside>

      <ResizeHandle
        onResize={handleResize}
        minWidth={MIN_SIDEBAR_WIDTH}
        maxWidth={MAX_SIDEBAR_WIDTH}
      />

      <main className="main-content">
        {isKnowledge && <SearchBar />}
        <Outlet />
      </main>
    </div>
  )
}
