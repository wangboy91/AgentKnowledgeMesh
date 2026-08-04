import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Document } from '../api/client'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Document[]>([])
  const [showResults, setShowResults] = useState(false)
  const navigate = useNavigate()
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length >= 2) {
        search(query)
      } else {
        setResults([])
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  async function search(q: string) {
    try {
      const res = await api.search(q, 10)
      setResults(res.documents)
      setShowResults(true)
    } catch (err) {
      console.error('Search failed:', err)
    }
  }

  function handleSelect(doc: Document) {
    navigate(`/knowledge/${doc.path}`)
    setQuery('')
    setShowResults(false)
  }

  return (
    <div className="search-container" ref={wrapperRef} style={{ position: 'relative' }}>
      <input
        type="text"
        className="search-input"
        placeholder="Search knowledge base..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setShowResults(true)}
      />

      {showResults && results.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: '16px',
          right: '16px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          maxHeight: '400px',
          overflowY: 'auto',
          zIndex: 100,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          {results.map((doc) => (
            <div
              key={doc.id}
              onClick={() => handleSelect(doc)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderBottom: '1px solid var(--border-color)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ fontWeight: 500 }}>{doc.title}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{doc.path}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
