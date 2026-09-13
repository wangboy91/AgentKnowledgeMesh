import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, SystemStats, ScanStats, VectorStats, RagIndexResponse } from '../api/client'

export default function Dashboard() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null)
  const [scanning, setScanning] = useState(false)
  const [indexing, setIndexing] = useState(false)
  const [lastScan, setLastScan] = useState<ScanStats | null>(null)
  const [lastIndex, setLastIndex] = useState<RagIndexResponse | null>(null)
  const admin = isAdmin()

  useEffect(() => {
    loadStats()
  }, [])

  async function loadStats() {
    try {
      const [data, vStats] = await Promise.all([
        api.getStats(),
        api.getVectorStats().catch(() => null),
      ])
      setStats(data)
      setVectorStats(vStats)
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

  async function handleIndex() {
    setIndexing(true)
    try {
      const result = await api.ragIndex()
      setLastIndex(result)
      await loadStats()
    } catch (err) {
      console.error('Index failed:', err)
    } finally {
      setIndexing(false)
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="dashboard">
      <h2 style={{ marginBottom: '24px' }}>{t('dashboard.title')}</h2>

      <div className="stats-grid">
        <div className="stat-card">
          <h3>{stats?.total_documents ?? '-'}</h3>
          <p>{t('dashboard.totalDocuments')}</p>
        </div>
        <div className="stat-card">
          <h3>{stats ? formatSize(stats.total_size_bytes) : '-'}</h3>
          <p>{t('dashboard.totalSize')}</p>
        </div>
        <div className="stat-card">
          <h3>{vectorStats?.total_chunks ?? '-'}</h3>
          <p>{t('dashboard.vectorChunks')}</p>
        </div>
      </div>

      {admin && (
        <div style={{ marginBottom: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
            {scanning ? t('dashboard.scanning') : `🔍 ${t('dashboard.scan')}`}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleIndex}
            disabled={indexing}
            style={{ background: 'var(--accent)' }}
          >
            {indexing ? t('dashboard.indexing') : `🧠 ${t('dashboard.indexAll')}`}
          </button>
        </div>
      )}

      {lastScan && (
        <div className="stat-card" style={{ maxWidth: '400px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>{t('dashboard.lastScan')}</h3>
          <p>✅ {t('dashboard.created')}: {lastScan.created}</p>
          <p>🔄 {t('dashboard.updated')}: {lastScan.updated}</p>
          <p>🗑️ {t('dashboard.deleted')}: {lastScan.deleted}</p>
        </div>
      )}

      {lastIndex && (
        <div className="stat-card" style={{ maxWidth: '400px', marginTop: '12px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '8px' }}>{t('dashboard.lastIndex')}</h3>
          <p>📄 {lastIndex.message}</p>
          <p>🧩 {t('dashboard.chunks')}: {lastIndex.total_chunks}</p>
        </div>
      )}

      <div style={{ marginTop: '32px', color: 'var(--text-secondary)' }}>
        <h3 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>{t('dashboard.quickStart')}</h3>
        <ol style={{ paddingLeft: '20px', lineHeight: 2 }}>
          <li>{t('dashboard.qs1')}</li>
          <li>{t('dashboard.qs2')}</li>
          <li>{t('dashboard.qs3')}</li>
          <li>{t('dashboard.qs4')}</li>
          <li>{t('dashboard.qs5')}</li>
        </ol>
      </div>
    </div>
  )
}
