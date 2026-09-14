/**
 * Dashboard · 总览指标 + 扫描 / RAG 索引触发 + 最近结果 + 快速开始
 */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  api,
  isAdmin,
  SystemStats,
  ScanStats,
  VectorStats,
  RagIndexResponse,
} from '../api/client'
import { formatSize as fmtSize } from '../utils/format'
import { useToast, useErrorReporter } from '../components/Toast'
import { ScanIcon, SparkleIcon } from '../components/Icon'

export default function Dashboard() {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
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
      reportError(err)
    }
  }

  async function handleScan() {
    if (!admin) return
    setScanning(true)
    try {
      const result = await api.scanDocuments()
      setLastScan(result)
      toast.success(
        t('dashboard.scanCompleted', {
          created: result.created,
          updated: result.updated,
          deleted: result.deleted,
        })
      )
      await loadStats()
    } catch (err) {
      reportError(err)
    } finally {
      setScanning(false)
    }
  }

  async function handleIndex() {
    if (!admin) return
    setIndexing(true)
    try {
      const result = await api.ragIndex()
      setLastIndex(result)
      toast.success(t('dashboard.indexCompleted', { indexed: result.indexed }))
      await loadStats()
    } catch (err) {
      reportError(err)
    } finally {
      setIndexing(false)
    }
  }

  const totalSize = stats ? fmtSize(stats.total_size_bytes) : null

  return (
    <div className="page">
      <h2>{t('dashboard.title')}</h2>
      <p className="page__desc">{t('dashboard.subtitle')}</p>

      <div className="stats-grid">
        <div className="card">
          <span className="card__label">{t('dashboard.totalDocuments')}</span>
          <span className="card__value">{stats?.total_documents ?? '—'}</span>
          <span className="card__hint">{t('dashboard.hintDocs')}</span>
        </div>
        <div className="card">
          <span className="card__label">{t('dashboard.totalSize')}</span>
          <span className="card__value">
            {totalSize ? `${totalSize.value} ${totalSize.unit}` : '—'}
          </span>
          <span className="card__hint">{t('dashboard.hintSize')}</span>
        </div>
        <div className="card">
          <span className="card__label">{t('dashboard.vectorChunks')}</span>
          <span className="card__value">{vectorStats?.total_chunks ?? '—'}</span>
          <span className="card__hint">{t('dashboard.hintChunks')}</span>
        </div>
        <div className="card">
          <span className="card__label">{t('dashboard.totalNodes')}</span>
          <span className="card__value">{stats?.total_nodes ?? '—'}</span>
          <span className="card__hint">
            {stats
              ? t('dashboard.hintNodes', { online: stats.online_nodes, total: stats.total_nodes })
              : t('dashboard.hintNodesEmpty')}
          </span>
        </div>
      </div>

      {admin && (
        <div className="card" style={{ marginBottom: 'var(--space-4)' }}>
          <strong style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
            {t('dashboard.actions')}
          </strong>
          <div className="settings-row">
            <button
              className="btn btn--primary"
              onClick={handleScan}
              disabled={scanning}
            >
              <ScanIcon size={14} />
              <span>{scanning ? t('dashboard.scanning') : t('dashboard.scan')}</span>
            </button>
            <button className="btn" onClick={handleIndex} disabled={indexing}>
              <SparkleIcon size={14} />
              <span>{indexing ? t('dashboard.indexing') : t('dashboard.indexAll')}</span>
            </button>
          </div>
        </div>
      )}

      {(lastScan || lastIndex) && (
        <div className="stats-grid">
          {lastScan && (
            <div className="card">
              <strong style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
                {t('dashboard.lastScan')}
              </strong>
              <Row label={t('dashboard.created')} value={lastScan.created} variant="success" />
              <Row label={t('dashboard.updated')} value={lastScan.updated} variant="warning" />
              <Row label={t('dashboard.deleted')} value={lastScan.deleted} variant="danger" />
            </div>
          )}
          {lastIndex && (
            <div className="card">
              <strong style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
                {t('dashboard.lastIndex')}
              </strong>
              <Row label={t('dashboard.chunks')} value={lastIndex.total_chunks} variant="accent" />
              <Row label={t('dashboard.indexed')} value={lastIndex.indexed} variant="success" />
            </div>
          )}
        </div>
      )}

      <section className="card" style={{ marginTop: 'var(--space-4)' }}>
        <strong style={{ display: 'block', marginBottom: 'var(--space-3)' }}>
          {t('dashboard.quickStart')}
        </strong>
        <ol style={{ paddingLeft: 'var(--space-5)', lineHeight: 2, color: 'var(--color-text-muted)' }}>
          <li>{t('dashboard.qs1')}</li>
          <li>{t('dashboard.qs2')}</li>
          <li>{t('dashboard.qs3')}</li>
          <li>{t('dashboard.qs4')}</li>
          <li>{t('dashboard.qs5')}</li>
        </ol>
      </section>
    </div>
  )
}

function Row({
  label,
  value,
  variant,
}: { label: string; value: number; variant: 'success' | 'warning' | 'danger' | 'accent' }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
      <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span className={`badge badge--${variant}`}>{value}</span>
    </div>
  )
}
