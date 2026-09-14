/**
 * 搜索框 · 嵌入 Topbar,占据中间区域
 * - 双模式:Semantic (RAG) / Keyword (BM25-ish)
 * - 300ms debounce,失焦不立即关闭(防止点结果时消失)
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, RagSearchResult } from '../api/client'
import { SearchIcon, SparkleIcon } from './Icon'

type Mode = 'semantic' | 'keyword'

interface SearchBarProps {
  /** Called when a search result is selected (used to close mobile search overlay) */
  onResultClick?: () => void
}

export default function SearchBar({ onResultClick }: SearchBarProps = {}) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RagSearchResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [mode, setMode] = useState<Mode>('semantic')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (query.length < 2) {
      setResults([])
      setShowResults(false)
      return
    }
    const timer = setTimeout(() => doSearch(query), 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, mode])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function doSearch(q: string) {
    setLoading(true)
    try {
      if (mode === 'semantic') {
        const res = await api.ragSearch(q, 10)
        setResults(res.results)
      } else {
        const res = await api.search(q, 10)
        setResults(
          res.documents.map((doc) => ({
            doc_id: doc.id,
            title: doc.title,
            path: doc.path,
            node_id: doc.node_id,
            chunk: '',
            score: 0,
          }))
        )
      }
      setShowResults(true)
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(result: RagSearchResult) {
    navigate(`/knowledge/${result.path}`)
    setQuery('')
    setShowResults(false)
    onResultClick?.()
  }

  function toggleMode() {
    setMode((m) => (m === 'semantic' ? 'keyword' : 'semantic'))
    setResults([])
  }

  return (
    <div className="search" ref={wrapperRef}>
      <span style={{ position: 'absolute', left: 8, top: 8, color: 'var(--color-text-subtle)', pointerEvents: 'none' }}>
        <SearchIcon size={16} />
      </span>
      <input
        className="search__input"
        style={{ paddingLeft: 32 }}
        type="text"
        placeholder={mode === 'semantic' ? t('search.semanticPh') : t('search.keywordPh')}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setShowResults(true)}
        aria-label={t('search.semanticPh')}
      />
      <button
        className={`search__mode-toggle ${mode === 'semantic' ? 'is-semantic' : ''}`}
        onClick={toggleMode}
        title={mode === 'semantic' ? t('search.switchKeyword') : t('search.switchSemantic')}
        aria-label={mode === 'semantic' ? t('search.switchKeyword') : t('search.switchSemantic')}
      >
        {mode === 'semantic' ? <SparkleIcon size={14} /> : <SearchIcon size={14} />}
        <span>{mode === 'semantic' ? t('search.modeSemantic') : t('search.modeKeyword')}</span>
      </button>

      {showResults && results.length > 0 && (
        <div className="search__dropdown" role="listbox">
          {results.map((r, i) => (
            <div
              key={`${r.doc_id}-${i}`}
              className="search-result"
              role="option"
              aria-selected={false}
              onClick={() => handleSelect(r)}
            >
              <div className="search-result__row">
                <div className="search-result__title">{r.title}</div>
                {r.score > 0 && (
                  <span className="search-result__score">{(r.score * 100).toFixed(0)}%</span>
                )}
              </div>
              <div className="search-result__path">{r.path}</div>
              {r.chunk && <div className="search-result__chunk">{r.chunk}</div>}
            </div>
          ))}
        </div>
      )}

      {showResults && query.length >= 2 && results.length === 0 && !loading && (
        <div className="search__dropdown">
          <div className="search-empty">{t('search.noResults')}</div>
        </div>
      )}
    </div>
  )
}
