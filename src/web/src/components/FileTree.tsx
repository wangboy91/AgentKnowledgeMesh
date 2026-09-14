/**
 * 文件树 — 选中节点 + 当前选中文档高亮 + RAG 状态徽章 + 勾选模式批量操作
 *
 * 工具栏分两排:
 *   - 过滤行:状态过滤 + 全部展开/收起
 *   - 操作行:批量加入 RAG / 批量移除 RAG / 扫描
 *
 * 批量操作为"勾选模式":
 *   点批量按钮 → 进入 selectMode(对应方向),文件行出现 checkbox
 *   选完后按确认按钮执行,或再次点同一按钮 = 取消
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, isAdmin, Document } from '../api/client'
import { useSelectedNodeId } from '../KnowledgeCtx'
import {
  FolderIcon,
  FolderOpenIcon,
  FileIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ScanIcon,
  CheckIcon,
  HourglassIcon,
  BanIcon,
  XIcon,
  PlusIcon,
  MinusIcon,
} from './Icon'
import EmptyState from './EmptyState'
import { useToast, useErrorReporter } from './Toast'

interface TreeNode {
  [key: string]: TreeNode | { _title: string; _path: string; _rag_status?: string }
}

const RAG_STATUS: Record<
  string,
  { variant: 'success' | 'warning' | 'muted'; icon: React.ComponentType<any>; i18nKey: string }
> = {
  indexed:  { variant: 'success', icon: CheckIcon,    i18nKey: 'filetree.statusIndexed' },
  pending:  { variant: 'warning', icon: HourglassIcon, i18nKey: 'filetree.statusPending' },
  excluded: { variant: 'muted',   icon: BanIcon,      i18nKey: 'filetree.statusExcluded' },
}

type SelectMode = null | 'add' | 'remove'

function collectAllDirs(node: TreeNode, prefix = ''): string[] {
  const dirs: string[] = []
  for (const [name, value] of Object.entries(node)) {
    if (name.startsWith('_')) continue
    if (!(value as any)._path) {
      const p = prefix ? `${prefix}/${name}` : name
      dirs.push(p)
      dirs.push(...collectAllDirs(value as TreeNode, p))
    }
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

function saveExpanded(key: string, dirs: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(dirs))
  } catch {
    /* ignore */
  }
}

function ancestorDirs(filePath: string | undefined): string[] {
  if (!filePath) return []
  const parts = filePath.split('/').slice(0, -1)
  const dirs: string[] = []
  for (let i = 0; i < parts.length; i++) {
    dirs.push(parts.slice(0, i + 1).join('/'))
  }
  return dirs
}

interface Props {
  /** 受控展开集合(测试/演示用);不传则自管 */
  expanded?: string[]
  onToggleFolder?: (path: string) => void
  onSetExpanded?: (dirs: string[]) => void
}

export default function FileTree(props: Props) {
  const { t } = useTranslation()
  const toast = useToast()
  const reportError = useErrorReporter()
  const navigate = useNavigate()
  const { '*': currentPath } = useParams<{ '*': string }>()
  const selectedNodeId = useSelectedNodeId()
  const admin = isAdmin()

  const activePath = currentPath ?? null

  // 展开状态(自管持久化);null(全部)与 local 用不同 key,避免互相覆盖
  const expandKey = `akm.tree.${selectedNodeId ?? 'all'}`
  const [expanded, setExpanded] = useState<string[]>(() => loadExpanded(expandKey))
  useEffect(() => {
    setExpanded(loadExpanded(expandKey))
  }, [expandKey])

  const exp = props.expanded ?? expanded
  const setExp = props.onSetExpanded
    ? (dirs: string[]) => props.onSetExpanded!(dirs)
    : (dirs: string[]) => {
        setExpanded(dirs)
        saveExpanded(expandKey, dirs)
      }
  const toggleFolder = props.onToggleFolder
    ? (p: string) => props.onToggleFolder!(p)
    : (p: string) => {
        setExpanded((prev) => {
          const next = prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
          saveExpanded(expandKey, next)
          return next
        })
      }

  const [tree, setTree] = useState<TreeNode>({})
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)

  // 勾选模式
  const [selectMode, setSelectMode] = useState<SelectMode>(null)
  const [picked, setPicked] = useState<Set<string>>(new Set())

  // 退出勾选模式
  const exitSelectMode = useCallback(() => {
    setSelectMode(null)
    setPicked(new Set())
  }, [])

  // 进入 / 切换 勾选模式(点同一个按钮退出)
  function toggleSelectMode(mode: 'add' | 'remove') {
    if (selectMode === mode) {
      exitSelectMode()
    } else {
      setSelectMode(mode)
      setPicked(new Set())
    }
  }

  function togglePick(path: string) {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  // 数据加载仅随选中节点变化——点击文档会改 URL(activePath),
  // 若把 activePath 放进依赖,每次点选都会整树重拉(loading 闪烁)
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [t1, d] = await Promise.all([
        api.getDocumentTree(selectedNodeId ?? undefined),
        api.getDocuments(selectedNodeId ?? undefined),
      ])
      setTree(t1)
      setDocs(d)
    } catch (err) {
      reportError(err)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId])

  useEffect(() => {
    load()
  }, [load])

  // 从搜索结果/URL 跳转到文档时,把该文件的祖先目录补进展开集
  // (只改展开状态,不再触发数据请求)
  useEffect(() => {
    if (activePath) {
      const need = ancestorDirs(activePath)
      if (need.length) {
        setExpanded((prev) => {
          const miss = need.filter((d) => !prev.includes(d))
          if (!miss.length) return prev
          const next = [...prev, ...miss]
          saveExpanded(expandKey, next)
          return next
        })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePath, expandKey, selectedNodeId])

  // 切换节点/路径时退出勾选模式
  useEffect(() => {
    exitSelectMode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId, activePath])

  async function toggleRag(docPath: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!admin || busy) return
    const doc = docs.find((d) => d.path === docPath)
    if (!doc) return
    setBusy(true)
    try {
      await api.setDocumentRag(doc.id, doc.rag_status === 'excluded')
      await load()
      toast.success(t('filetree.ragUpdated'))
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function confirmBatch() {
    if (!admin || busy || !selectMode) return
    const target = Array.from(picked)
      .map((p) => docs.find((d) => d.path === p))
      .filter((d): d is Document => !!d)
      .map((d) => d.id)
    if (!target.length) return
    setBusy(true)
    try {
      await api.batchSetRag(target, selectMode === 'add')
      await load()
      toast.success(selectMode === 'add' ? t('filetree.ragBatchAdded') : t('filetree.ragBatchRemoved'))
      exitSelectMode()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleScan() {
    if (busy) return
    setBusy(true)
    try {
      const stats = await api.scanDocuments()
      toast.success(
        t('dashboard.scanCompleted', {
          created: stats.created,
          updated: stats.updated,
          deleted: stats.deleted,
        })
      )
      await load()
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  /**
   * 选中模式时,文件项是否可勾选:
   * - add 模式:只能选 excluded
   * - remove 模式:只能选 indexed/pending
   */
  function canPick(ragStatus: string | undefined): boolean {
    if (!selectMode) return false
    const s = ragStatus || 'indexed'
    return selectMode === 'add' ? s === 'excluded' : s !== 'excluded'
  }

  function renderNode(name: string, node: TreeNode | any, path = ''): React.ReactNode {
    const currentPath = path ? `${path}/${name}` : name

    if ((node as any)._path) {
      const nodePath = (node as any)._path as string
      const statusKey = (node as any)._rag_status || 'indexed'
      if (filter && statusKey !== filter) return null
      const status = RAG_STATUS[statusKey]
      const StatusIcon = status.icon
      const isActive = activePath === nodePath
      const isPicked = picked.has(nodePath)
      const pickable = canPick(statusKey)

      const cls = ['tree__item']
      if (isActive) cls.push('tree__item--active')
      if (selectMode && pickable) cls.push('tree__item--pickable')
      if (selectMode && isPicked) cls.push('tree__item--picked')

      return (
        <div
          key={nodePath}
          className={cls.join(' ')}
          role="button"
          tabIndex={0}
          aria-current={isActive ? 'page' : undefined}
          aria-selected={selectMode ? isPicked : undefined}
          onClick={() => {
            if (selectMode) {
              if (pickable) togglePick(nodePath)
              return
            }
            navigate(`/knowledge/${nodePath}`)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              if (selectMode) {
                if (pickable) togglePick(nodePath)
              } else {
                navigate(`/knowledge/${nodePath}`)
              }
            }
          }}
        >
          {selectMode && (
            <span
              className={`tree__check ${pickable ? '' : 'is-disabled'} ${isPicked ? 'is-checked' : ''}`}
              role="checkbox"
              aria-checked={isPicked}
              aria-disabled={!pickable}
              onClick={(e) => {
                e.stopPropagation()
                if (pickable) togglePick(nodePath)
              }}
            >
              {isPicked && <CheckIcon size={10} />}
            </span>
          )}
          <span className="tree__icon" aria-hidden>
            <FileIcon size={14} />
          </span>
          <span className="tree__label">{node._title || name}</span>
          {!selectMode && admin && (
            <button
              className={`tree__rag tree__rag--${status.variant}`}
              onClick={(e) => toggleRag(nodePath, e)}
              title={t(status.i18nKey)}
              aria-label={t(status.i18nKey)}
            >
              <StatusIcon size={12} />
            </button>
          )}
        </div>
      )
    }

    const isExpanded = exp.includes(currentPath)
    const children = Object.entries(node)
      .filter(([key]) => !key.startsWith('_'))
      .sort(([a, aNode], [b, bNode]) => {
        const aIsFolder = !(aNode as any)._path
        const bIsFolder = !(bNode as any)._path
        if (aIsFolder && !bIsFolder) return -1
        if (!aIsFolder && bIsFolder) return 1
        return a.localeCompare(b)
      })
    const folderCls = ['tree__item']
    if (isExpanded) folderCls.push('tree__item--expanded')

    return (
      <div key={currentPath}>
        <div
          className={folderCls.join(' ')}
          role="button"
          tabIndex={0}
          aria-expanded={isExpanded}
          onClick={() => toggleFolder(currentPath)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              toggleFolder(currentPath)
            }
          }}
        >
          <span className="tree__toggle" aria-hidden>
            <ChevronRightIcon size={10} />
          </span>
          <span className="tree__icon" aria-hidden>
            {isExpanded ? <FolderOpenIcon size={14} /> : <FolderIcon size={14} />}
          </span>
          <span className="tree__label">{name}</span>
        </div>
        {isExpanded && (
          <div className="tree__children">
            {children.map(([childName, childNode]) =>
              renderNode(childName, childNode, currentPath)
            )}
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="panel panel__body">
        <EmptyState icon={<FileIcon size={28} />} title={t('common.loading')} />
      </div>
    )
  }

  if (Object.keys(tree).length === 0) {
    return (
      <div className="panel panel__body">
        <EmptyState
          icon={<FileIcon size={28} />}
          title={t('filetree.noDocuments')}
          desc={t('filetree.scanHint')}
          actions={
            <button className="btn btn--primary" onClick={handleScan} disabled={busy}>
              <ScanIcon size={14} />
              <span>{t('filetree.scanNow')}</span>
            </button>
          }
        />
      </div>
    )
  }

  return (
    <div className="tree">
      {/* ============ 工具栏 ============ */}
      <div className="tree-toolbar">
        {/* 第一排:过滤 + 全部展开/收起 */}
        <div className="tree-toolbar__row">
          <button
            className="icon-btn icon-btn--ghost"
            onClick={() => setExp(collectAllDirs(tree))}
            aria-label={t('filetree.expandAll')}
            title={t('filetree.expandAll')}
          >
            <ChevronDownIcon size={14} />
            <ChevronDownIcon size={14} style={{ marginLeft: -6 }} />
          </button>
          <button
            className="icon-btn icon-btn--ghost"
            onClick={() => setExp([])}
            aria-label={t('filetree.collapseAll')}
            title={t('filetree.collapseAll')}
          >
            <ChevronRightIcon size={14} />
            <ChevronRightIcon size={14} style={{ marginLeft: -6 }} />
          </button>
          <select
            className="select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label={t('filetree.allStatus')}
            title={t('filetree.allStatus')}
          >
            <option value="">{t('filetree.allStatus')}</option>
            <option value="indexed">{t('filetree.statusIndexed')}</option>
            <option value="pending">{t('filetree.statusPending')}</option>
            <option value="excluded">{t('filetree.statusExcluded')}</option>
          </select>
          {admin && (
            <button
              className="icon-btn icon-btn--ghost"
              onClick={handleScan}
              aria-label={t('filetree.scanNow')}
              title={t('filetree.scanNow')}
            >
              <ScanIcon size={14} />
            </button>
          )}
        </div>

        {/* 第二排:批量操作(勾选模式) */}
        {admin && (
          <div className="tree-toolbar__row">
            {!selectMode ? (
              <>
                <button
                  className="btn btn--sm"
                  onClick={() => toggleSelectMode('add')}
                  title={t('filetree.ragAdd')}
                >
                  <PlusIcon size={12} />
                  <span>{t('filetree.ragAdd')}</span>
                </button>
                <button
                  className="btn btn--sm"
                  onClick={() => toggleSelectMode('remove')}
                  title={t('filetree.ragRemove')}
                >
                  <MinusIcon size={12} />
                  <span>{t('filetree.ragRemove')}</span>
                </button>
              </>
            ) : (
              <>
                <span className="tree-toolbar__hint">
                  {selectMode === 'add'
                    ? t('filetree.pickToAdd', { count: picked.size })
                    : t('filetree.pickToRemove', { count: picked.size })}
                </span>
                <button
                  className="btn btn--sm btn--ghost"
                  onClick={exitSelectMode}
                  title={t('common.cancel')}
                >
                  <XIcon size={12} />
                  <span>{t('common.cancel')}</span>
                </button>
                <button
                  className={`btn btn--sm ${selectMode === 'add' ? 'btn--primary' : 'btn--danger'}`}
                  onClick={confirmBatch}
                  disabled={busy || !picked.size}
                  title={selectMode === 'add' ? t('filetree.ragAdd') : t('filetree.ragRemove')}
                >
                  {selectMode === 'add' ? <PlusIcon size={12} /> : <MinusIcon size={12} />}
                  <span>
                    {selectMode === 'add' ? t('filetree.ragAdd') : t('filetree.ragRemove')}
                    {' '}({picked.size})
                  </span>
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* ============ 树 ============ */}
      {Object.entries(tree).map(([name, node]) => renderNode(name, node))}
    </div>
  )
}