import { useState, useEffect } from 'react'
import { api, SystemStats, ScanStats } from '../api/client'

export default function Dashboard() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [scanning, setScanning] = useState(false)
  const [lastScan, setLastScan] = useState<ScanStats | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  async function loadStats() {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (err) {
      console.error('Failed to load stats:', err)
    }
  }

  async function handleScan() {
    setScanning(true)
    try {
      const result = await api.scanDocuments()
      setLastScan(result)
      await loadStats()
    } catch (err) {
      console.error('Scan failed:', err)
    } finally {
      setScanning(false)
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="dashboard">
      <h2 style={{ marginBottom: '24px' }}>Dashboard</h2>

      <div className="stats-grid">
        <div className="stat-card">
          <h3>{stats?.total_documents ?? '-'}</h3>
          <p>Total Documents</p>
        </div>
        <div className="stat-card">
          <h3>{stats ? formatSize(stats.total_size_bytes) : '-'}</h3>
          <p>Total Size</p>
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
          {scanning ? 'Scanning...' : '🔍 Scan Knowledge Base'}
        </button>
      </div>

      {lastScan && (
        <div className="stat-card" style={{ maxWidth: '400px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>Last Scan Result</h3>
          <p>✅ Created: {lastScan.created}</p>
          <p>🔄 Updated: {lastScan.updated}</p>
          <p>🗑️ Deleted: {lastScan.deleted}</p>
        </div>
      )}

      <div style={{ marginTop: '32px', color: 'var(--text-secondary)' }}>
        <h3 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>Quick Start</h3>
        <ol style={{ paddingLeft: '20px', lineHeight: 2 }}>
          <li>Place your Markdown files in the knowledge directory</li>
          <li>Click "Scan Knowledge Base" to index them</li>
          <li>Browse files in the Knowledge tab</li>
          <li>Use the search bar to find content</li>
        </ol>
      </div>
    </div>
  )
}
