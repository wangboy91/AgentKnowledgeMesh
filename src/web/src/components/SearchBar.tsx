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
        <div className="search-dropdown">
          {results.map((doc) => (
            <div
              key={doc.id}
              className="search-result-item"
              onClick={() => handleSelect(doc)}
            >
              <div className="search-result-title">{doc.title}</div>
              <div className="search-result-path">{doc.path}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
