import { useState, useCallback, useEffect } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useTheme } from '../ThemeContext'
import { getSession, logout } from '../api/client'
import FileTree from './FileTree'
import NodeList from './NodeList'
import SearchBar from './SearchBar'
import ResizeHandle from './ResizeHandle'
import { KnowledgeProvider } from '../KnowledgeCtx'
import { getLang, setLang, type Lang } from '../i18n'

const DEFAULT_SIDEBAR_WIDTH = 220
const MIN_SIDEBAR_WIDTH = 160
const MAX_SIDEBAR_WIDTH = 360

/** 由知识库文档路径推导其祖先目录 */
function ancestorDirs(filePath: string): string[] {
  const parts = filePath.split('/').slice(0, -1)
  const dirs: string[] = []
  for (let i = 0; i < parts.length; i++) {
    dirs.push(parts.slice(0, i + 1).join('/'))
  }
  return dirs
}

function loadExpanded(key: string): string[] {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveExpanded(key: string, dirs: string[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(dirs))
  } catch {
    /* 存储不可用时降级为仅当次会话 */
  }
}

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { theme, toggleTheme } = useTheme()
  const isKnowledge = location.pathname.startsWith('/knowledge')
  const isNodes = location.pathname.startsWith('/nodes')
  const isSettings = location.pathname.startsWith('/settings')
  const session = getSession()

  function handleLogout() {
    logout()
    window.dispatchEvent(new CustomEvent('akm:unauthorized'))
    navigate('/')
  }

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('agentvault-sidebar-width')
    return saved ? parseInt(saved, 10) : DEFAULT_SIDEBAR_WIDTH
  })

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [lang, setLangState] = useState<Lang>(getLang())

  function handleLang(next: Lang) {
    setLang(next)
    setLangState(next)
  }

  // 展开状态:按节点持久化 localStorage(key = akm.tree.<node_id>,Local 用 'local')
  const expandKey = `akm.tree.${selectedNodeId ?? 'local'}`
  const [expanded, setExpanded] = useState<string[]>(() =>
    loadExpanded(`akm.tree.${selectedNodeId ?? 'local'}`)
  )

  useEffect(() => {
    setExpanded(loadExpanded(expandKey))
  }, [expandKey])

  const toggleFolder = useCallback(
    (path: string) => {
      setExpanded((prev) => {
        const next = prev.includes(path)
          ? prev.filter((p) => p !== path)
          : [...prev, path]
        saveExpanded(expandKey, next)
        return next
      })
    },
    [expandKey]
  )

  // 全部展开/收起:由 FileTree 计算目标目录集合作一次性设置
  const setExpandedAll = useCallback(
    (dirs: string[]) => {
      setExpanded(dirs)
      saveExpanded(expandKey, dirs)
    },
    [expandKey]
  )

  // 路由变更(命中搜索跳转):按 path 逐段展开祖先目录
  useEffect(() => {
    if (!isKnowledge) return
    const path = decodeURIComponent(location.pathname.replace(/^\/knowledge\/?/, ''))
    if (!path) return
    const dirs = ancestorDirs(path)
    if (!dirs.length) return
    setExpanded((prev) => {
      const missing = dirs.filter((d) => !prev.includes(d))
      if (!missing.length) return prev
      const next = [...prev, ...missing]
      saveExpanded(expandKey, next)
      return next
    })
  }, [location.pathname, isKnowledge, expandKey])

  const handleResize = useCallback((width: number) => {
    setSidebarWidth(width)
    localStorage.setItem('agentvault-sidebar-width', width.toString())
  }, [])

  return (
    <div className="app-layout">
      <aside className="sidebar" style={{ width: sidebarWidth }}>
        <div className="sidebar-header">
          <div className="sidebar-header-left">
            <h1>{t('layout.headerTitle')}</h1>
            <p>{t('layout.headerSubtitle')}</p>
          </div>
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>

        <nav style={{ padding: '12px 8px', borderBottom: '1px solid var(--border-color)' }}>
          <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
            {t('nav.dashboard')}
          </Link>
          <Link to="/knowledge" className={`nav-link ${isKnowledge ? 'active' : ''}`}>
            {t('nav.knowledge')}
          </Link>
          <Link to="/nodes" className={`nav-link ${isNodes ? 'active' : ''}`}>
            {t('nav.nodes')}
          </Link>
          <Link to="/settings" className={`nav-link ${isSettings ? 'active' : ''}`}>
            {t('nav.settings')}
          </Link>
        </nav>

        {session && (
          <div
            style={{
              padding: '10px 12px',
              marginTop: 'auto',
              borderTop: '1px solid var(--border-color)',
              fontSize: 13,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span title={session.username}>
                {t('layout.loginAs', { username: session.username })}
                <span style={{ color: 'var(--text-secondary, #888)' }}> ({session.role})</span>
              </span>
              <button onClick={handleLogout} title={t('common.logout')} style={{ cursor: 'pointer' }}>
                {t('common.logout')}
              </button>
            </div>
            <div style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--text-secondary, #888)' }}>{t('layout.langLabel')}</span>
              <button
                onClick={() => handleLang('zh')}
                style={{ cursor: 'pointer', fontWeight: lang === 'zh' ? 700 : 400 }}
              >
                中文
              </button>
              <button
                onClick={() => handleLang('en')}
                style={{ cursor: 'pointer', fontWeight: lang === 'en' ? 700 : 400 }}
              >
                EN
              </button>
            </div>
          </div>
        )}

        {isKnowledge && (
          <div
            className="node-list-pane"
            style={{ padding: '8px', borderTop: '1px solid var(--border-color)', overflowY: 'auto' }}
          >
            <NodeList onSelectNode={setSelectedNodeId} selectedNodeId={selectedNodeId} />
          </div>
        )}
      </aside>

      {isKnowledge && (
        <section className="tree-pane" aria-label={t('layout.paneTree')}>
          <FileTree
            selectedNodeId={selectedNodeId}
            expanded={expanded}
            onToggleFolder={toggleFolder}
            onSetExpanded={setExpandedAll}
          />
        </section>
      )}

      <ResizeHandle
        onResize={handleResize}
        minWidth={MIN_SIDEBAR_WIDTH}
        maxWidth={MAX_SIDEBAR_WIDTH}
      />

      <main className="main-content">
        <KnowledgeProvider value={{ selectedNodeId }}>
          {isKnowledge && <SearchBar />}
          <Outlet />
        </KnowledgeProvider>
      </main>
    </div>
  )
}