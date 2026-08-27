import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, RagSearchResult } from '../api/client'

type SearchMode = 'semantic' | 'keyword'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RagSearchResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [mode, setMode] = useState<SearchMode>('semantic')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length >= 2) {
        doSearch(query)
      } else {
        setResults([])
      }
    }, 300)

    return () => clearTimeout(timer)
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
        // 将关键词搜索结果转为统一格式
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
  }

  function toggleMode() {
    setMode((m) => (m === 'semantic' ? 'keyword' : 'semantic'))
    setResults([])
  }

  return (
    <div className="search-container" ref={wrapperRef} style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <input
          type="text"
          className="search-input"
          placeholder={mode === 'semantic' ? 'Semantic search...' : 'Keyword search...'}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setShowResults(true)}
          style={{ flex: 1 }}
        />
        <button
          onClick={toggleMode}
          title={mode === 'semantic' ? 'Switch to keyword search' : 'Switch to semantic search'}
          style={{
            background: mode === 'semantic' ? 'var(--accent)' : 'var(--bg-secondary)',
            color: mode === 'semantic' ? '#fff' : 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '4px 8px',
            cursor: 'pointer',
            fontSize: '12px',
            whiteSpace: 'nowrap',
          }}
        >
          {mode === 'semantic' ? '🧠' : '🔤'}
        </button>
      </div>

      {showResults && results.length > 0 && (
        <div className="search-dropdown">
          {results.map((r, i) => (
            <div
              key={`${r.doc_id}-${i}`}
              className="search-result-item"
              onClick={() => handleSelect(r)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="search-result-title">{r.title}</div>
                {r.score > 0 && (
                  <span style={{ fontSize: '11px', color: 'var(--accent)', flexShrink: 0, marginLeft: '8px' }}>
                    {(r.score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div className="search-result-path">{r.path}</div>
              {r.chunk && (
                <div style={{
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                  marginTop: '4px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                }}>
                  {r.chunk}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showResults && query.length >= 2 && results.length === 0 && !loading && (
        <div className="search-dropdown">
          <div style={{ padding: '12px', color: 'var(--text-secondary)', textAlign: 'center', fontSize: '13px' }}>
            No results found
          </div>
        </div>
      )}
    </div>
  )
}
