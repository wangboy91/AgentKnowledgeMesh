/**
 * 节点列表(侧栏专用) — 简洁列表 + 平台图标 + 在线状态点
 */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api, Node } from '../api/client'
import { useToast } from './Toast'
import { HomeIcon, ListIcon } from './Icon'

interface Props {
  onSelectNode?: (nodeId: string | null) => void
  selectedNodeId?: string | null
}

function platformIcon(platform: string) {
  const map: Record<string, string> = {
    darwin: '🍎',
    windows: '🪟',
    linux: '🐧',
  }
  return map[platform] ?? '💻'
}

export default function NodeList({ onSelectNode, selectedNodeId }: Props) {
  const { t } = useTranslation()
  const toast = useToast()
  const [nodes, setNodes] = useState<Node[]>([])
  const [loading, setLoading] = useState(true)

  const loadNodes = async () => {
    try {
      const data = await api.getNodes()
      setNodes(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      if (!msg.includes('Session')) toast.danger(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNodes()
    const interval = setInterval(loadNodes, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="node-list__empty">{t('common.loading')}</div>
  }

  return (
    <div className="node-list">
      {/* 全部:所有节点 + hub 本机目录的并集 */}
      <div
        className={`node-item ${selectedNodeId === null ? 'is-active' : ''}`}
        onClick={() => onSelectNode?.(null)}
        role="button"
        tabIndex={0}
        aria-pressed={selectedNodeId === null}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onSelectNode?.(null)
          }
        }}
      >
        <span className="node-item__icon" aria-hidden>
          <ListIcon size={14} />
        </span>
        <span className="node-item__name">{t('nodes.all')}</span>
      </div>

      {/* Local:hub 端配置目录(本机扫描,node_id="local");不是"当前机器作为节点" */}
      <div
        className={`node-item ${selectedNodeId === 'local' ? 'is-active' : ''}`}
        onClick={() => onSelectNode?.('local')}
        role="button"
        tabIndex={0}
        aria-pressed={selectedNodeId === 'local'}
        title={`Local · ${t('nodes.local')}`}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onSelectNode?.('local')
          }
        }}
      >
        <span className="node-item__icon" aria-hidden>
          <HomeIcon size={14} />
        </span>
        <span className="node-item__name">Local</span>
        <span className="node-item__status node-item__status--online" aria-label="online" />
      </div>

      {nodes.map((node) => (
        <div
          key={node.id}
          className={`node-item ${selectedNodeId === node.id ? 'is-active' : ''}`}
          onClick={() => onSelectNode?.(node.id)}
          role="button"
          tabIndex={0}
          aria-pressed={selectedNodeId === node.id}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onSelectNode?.(node.id)
            }
          }}
          title={`${node.name} · ${node.platform}${node.ip ? ` · ${node.ip}` : ''}`}
        >
          <span className="node-item__icon" aria-hidden>
            <span>{platformIcon(node.platform)}</span>
          </span>
          <span className="node-item__name">{node.name}</span>
          <span
            className={`node-item__status node-item__status--${node.status}`}
            aria-label={node.status}
          />
        </div>
      ))}

      {nodes.length === 0 && (
        <div className="node-list__empty">
          <div>{t('nodes.noNodes')}</div>
          <div className="node-list__empty-hint">{t('nodes.nodeHint')}</div>
        </div>
      )}
    </div>
  )
}
