import { useState, useEffect, useCallback } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useTheme } from '../ThemeContext'
import { getSession, logout } from '../api/client'
import NodeList from './NodeList'
import SearchBar from './SearchBar'
import ResizeHandle from './ResizeHandle'
import { KnowledgeProvider } from '../KnowledgeCtx'
import { getLang, setLang, type Lang } from '../i18n'
import {
  SunIcon,
  MoonIcon,
  DashboardIcon,
  BookIcon,
  GlobeIcon,
  SettingsIcon,
  MenuIcon,
  LogoutIcon,
  CollapseIcon,
  ExpandIcon,
} from './Icon'

const DEFAULT_SIDEBAR_WIDTH = 240
const MIN_SIDEBAR_WIDTH = 200
const MAX_SIDEBAR_WIDTH = 320

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

  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    const saved = localStorage.getItem('akm.sidebar')
    return saved ? parseInt(saved, 10) : DEFAULT_SIDEBAR_WIDTH
  })

  // 选中节点状态(Knowledge 页 FileTree 通过 KnowledgeCtx 共享)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Tree pane 显隐(只在 Knowledge 页生效)
  const [treeVisible, setTreeVisible] = useState<boolean>(() => {
    return localStorage.getItem('akm.tree.visible') !== 'collapsed'
  })
  const toggleTree = useCallback(() => {
    setTreeVisible((v) => {
      const next = !v
      localStorage.setItem('akm.tree.visible', next ? 'visible' : 'collapsed')
      return next
    })
  }, [])

  const [lang, setLangState] = useState<Lang>(getLang())
  const [sidebarOpen, setSidebarOpen] = useState(false)

  function handleLang(next: Lang) {
    setLang(next)
    setLangState(next)
  }

  const handleResize = (width: number) => {
    setSidebarWidth(width)
    localStorage.setItem('akm.sidebar', width.toString())
  }

  // 路由变化时关闭移动端抽屉
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // 顶部 breadcrumb · 根据当前路径推导
  const breadcrumbs = (() => {
    if (location.pathname === '/') return [{ key: 'dashboard', label: t('nav.dashboard'), icon: <DashboardIcon /> }]
    if (isKnowledge) return [{ key: 'knowledge', label: t('nav.knowledge'), icon: <BookIcon /> }]
    if (isNodes) return [{ key: 'nodes', label: t('nav.nodes'), icon: <GlobeIcon /> }]
    if (isSettings) return [{ key: 'settings', label: t('nav.settings'), icon: <SettingsIcon /> }]
    return []
  })()

  // 当前选中的文档路径(用于 Topbar 显示)
  const currentDocPath =
    isKnowledge ? decodeURIComponent(location.pathname.replace(/^\/knowledge\/?/, '')) : null

  return (
    <div
      className="app"
      style={{
        ['--sidebar-w' as any]: `${sidebarWidth}px`,
      }}
    >
      {/* ========================== Sidebar ========================== */}
      <aside
        className={`app-sidebar ${sidebarOpen ? 'is-open' : ''}`}
        aria-label={t('layout.headerTitle')}
      >
        <div className="sidebar-brand">
          <div className="sidebar-brand__title">
            <h1>{t('layout.headerTitle')}</h1>
            <p>{t('layout.headerSubtitle')}</p>
          </div>
          <button
            className="icon-btn icon-btn--ghost"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? t('layout.themeLight') : t('layout.themeDark')}
            title={theme === 'dark' ? t('layout.themeLight') : t('layout.themeDark')}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>

        <nav className="nav" aria-label={t('layout.navPrimary')}>
          <Link to="/" className={`nav__item ${location.pathname === '/' ? 'nav__item--active' : ''}`}>
            <DashboardIcon className="nav__item__icon" />
            <span>{t('nav.dashboard')}</span>
          </Link>
          <Link
            to="/knowledge"
            className={`nav__item ${isKnowledge ? 'nav__item--active' : ''}`}
          >
            <BookIcon className="nav__item__icon" />
            <span>{t('nav.knowledge')}</span>
          </Link>
          <Link
            to="/nodes"
            className={`nav__item ${isNodes ? 'nav__item--active' : ''}`}
          >
            <GlobeIcon className="nav__item__icon" />
            <span>{t('nav.nodes')}</span>
          </Link>
          <Link
            to="/settings"
            className={`nav__item ${isSettings ? 'nav__item--active' : ''}`}
          >
            <SettingsIcon className="nav__item__icon" />
            <span>{t('nav.settings')}</span>
          </Link>
        </nav>

        {/* Knowledge 页专属:节点列表 */}
        {isKnowledge && (
          <div className="app-sidebar__section">
            <div className="app-sidebar__section-label">
              <span>{t('layout.nodesLabel')}</span>
            </div>
            <NodeList
              onSelectNode={setSelectedNodeId}
              selectedNodeId={selectedNodeId}
            />
          </div>
        )}

        {/* Footer(用户/语言/退出) */}
        {session && (
          <div className="app-sidebar__footer">
            <div className="app-sidebar__footer-row">
              <div className="app-sidebar__user">
                <span className="truncate app-sidebar__user-name">
                  {t('layout.loginAs', { username: session.username })}
                </span>
                <span className="app-sidebar__role">{session.role}</span>
              </div>
              <button
                className="icon-btn icon-btn--ghost"
                onClick={handleLogout}
                aria-label={t('common.logout')}
                title={t('common.logout')}
              >
                <LogoutIcon />
              </button>
            </div>
            <div className="app-sidebar__lang" role="group" aria-label={t('layout.langLabel')}>
              <button
                onClick={() => handleLang('zh')}
                className={lang === 'zh' ? 'is-active' : ''}
                aria-pressed={lang === 'zh'}
              >
                中文
              </button>
              <button
                onClick={() => handleLang('en')}
                className={lang === 'en' ? 'is-active' : ''}
                aria-pressed={lang === 'en'}
              >
                EN
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* ========================== Resize Handle ========================== */}
      <ResizeHandle
        onResize={handleResize}
        minWidth={MIN_SIDEBAR_WIDTH}
        maxWidth={MAX_SIDEBAR_WIDTH}
      />

      {/* ========================== Main ========================== */}
      <main className="app-main">
        <KnowledgeProvider value={{ selectedNodeId, treeVisible, toggleTree }}>
          {/* Topbar */}
          <div className="topbar">
            <button
              className="icon-btn icon-btn--ghost lg-only-toggle"
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label={t('layout.toggleSidebar')}
              title={t('layout.toggleSidebar')}
              style={{ marginRight: 4 }}
            >
              <MenuIcon />
            </button>

            {isKnowledge && (
              <button
                className="icon-btn icon-btn--ghost"
                onClick={toggleTree}
                aria-label={treeVisible ? t('layout.collapseTree') : t('layout.expandTree')}
                title={treeVisible ? t('layout.collapseTree') : t('layout.expandTree')}
                style={{ marginRight: 4 }}
              >
                {treeVisible ? <CollapseIcon /> : <ExpandIcon />}
              </button>
            )}

            <nav className="topbar__breadcrumbs" aria-label={t('layout.breadcrumbs')}>
              {breadcrumbs.map((b, i) => (
                <span key={b.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  {i > 0 && <span style={{ color: 'var(--color-text-subtle)' }}>/</span>}
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {b.icon}
                    <span>{b.label}</span>
                  </span>
                </span>
              ))}
              {currentDocPath && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ color: 'var(--color-text-subtle)' }}>/</span>
                  <strong className="truncate" style={{ maxWidth: 360 }}>
                    {currentDocPath.split('/').pop()}
                  </strong>
                </span>
              )}
            </nav>

            <div className="topbar__spacer" />

            {isKnowledge && <SearchBar />}
          </div>

          {/* Content */}
          <div className="app-content">
            <Outlet />
          </div>
        </KnowledgeProvider>
      </main>
    </div>
  )
}
