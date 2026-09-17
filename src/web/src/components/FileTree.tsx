import { useRef } from 'react'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api, isAdmin } from '../api/client'
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
  RefreshIcon,
} from './Icon'
import EmptyState from './EmptyState'
import { useToast, useErrorReporter } from './Toast'
import { encodeDocPath } from '../utils/format'

/**
 * 折叠懒加载文件树:展开某目录时按 dir 切片请求其一层直接子项,
 * 传输量 O(可见目录)而非 O(全量文档)。目录内容缓存在本地
 * (childrenByDir),切走节点后清空;「全部展开」回退到一次全量请求。
 * 注意:RAG 状态 filter 作用于"已加载且已展开"的范围。
 */

interface TreeNode {
  [key: string]: TreeNode | { _title: string; _path: string; _rag_status?: string; id: number }
}

type DirChildren = Record<string, Record<string, any>>

const RAG_STATUS: Record<
  string,
  { variant: 'success' | 'warning' | 'muted'; icon: React.ComponentType<any>; i18nKey: string }
> = {
  indexed:  { variant: 'success', icon: CheckIcon,    i18nKey: 'filetree.statusIndexed' },
  pending:  { variant: 'warning', icon: HourglassIcon, i18nKey: 'filetree.statusPending' },
  excluded: { variant: 'muted',   icon: BanIcon,      i18nKey: 'filetree.statusExcluded' },
}

type SelectMode = null | 'add' | 'remove'

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

/** 把全量树拆成平铺的一层一层子项(供「全部展开」一次加载后使用) */
function decompose(full: Record<string, any>): { byDir: DirChildren; allDirs: string[] } {
  const byDir: DirChildren = {}
  const allDirs: string[] = []
  const walk = (node: Record<string, any>, curDir: string) => {
    const children: Record<string, any> = {}
    byDir[curDir] = children
    if (curDir) allDirs.push(curDir)
    for (const [name, value] of Object.entries(node)) {
      if ((value as any)._path) {
        children[name] = value // 叶子原样(incl. id)
      } else {
        children[name] = {}
        walk(value, curDir ? `${curDir}/${name}` : name)
      }
    }
  }
  walk(full, '')
  return { byDir, allDirs }
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

  // ---- 懒加载数据(平铺目录缓存)----
  const [cache, setCache] = useState<DirChildren>({})
  const cacheRef = useRef<DirChildren>({})
  const inflightRef = useRef<Record<string, Promise<void>>>({})
  // 每目录代际:reload/切节点时递增,使在途旧响应失效(不依赖 promise 自比较)
  const epochRef = useRef<Record<string, number>>({})
  const nodeRef = useRef<string | null>(selectedNodeId)
  const [loadingDirs, setLoadingDirs] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)

  // 勾选模式
  const [selectMode, setSelectMode] = useState<SelectMode>(null)
  const [picked, setPicked] = useState<Map<string, number>>(new Map()) // path -> doc id

  // 退出勾选模式
  const exitSelectMode = useCallback(() => {
    setSelectMode(null)
    setPicked(new Map())
  }, [])

  // 进入 / 切换 勾选模式(点同一个按钮退出)
  function toggleSelectMode(mode: 'add' | 'remove') {
    if (selectMode === mode) {
      exitSelectMode()
    } else {
      setSelectMode(mode)
      setPicked(new Map())
    }
  }

  function togglePick(path: string, id: number | undefined) {
    setPicked((prev) => {
      const next = new Map(prev)
      if (next.has(path)) next.delete(path)
      else if (id !== undefined) next.set(path, id)
      return next
    })
  }

  /**
   * 加载并缓存一个目录的一层子项。幂等:
   * - 已缓存/T在途中 → 复用;完成后仅当"节点未切换且代际未变"才写缓存
   */
  const loadDir = useCallback(
    (dir: string): Promise<void> => {
      if (dir in cacheRef.current) return Promise.resolve()
      if (dir in inflightRef.current) return inflightRef.current[dir]!

      const nodeId = nodeRef.current
      const epoch = (epochRef.current[dir] ?? 0) + 1
      epochRef.current[dir] = epoch
      const req = (async () => {
        setLoadingDirs((prev) => new Set(prev).add(dir))
        try {
          const data = await api.getDocumentTree(nodeId ?? undefined, dir)
          if (nodeRef.current !== nodeId) return // 节点已切换,丢弃
          if (epochRef.current[dir] !== epoch) return // 已被 reload 作废,丢弃
          cacheRef.current[dir] = data
          setCache({ ...cacheRef.current })
        } catch (err) {
          if (epochRef.current[dir] === epoch) reportError(err)
        } finally {
          setLoadingDirs((prev) => {
            const next = new Set(prev)
            next.delete(dir)
            return next
          })
          if (epochRef.current[dir] === epoch) delete inflightRef.current[dir]
        }
      })()
      inflightRef.current[dir] = req
      return req
    },
    [reportError]
  )

  /** 作废并重载指定目录(代际+1,旧响应不会回写)。用于 RAG 操作 / 扫描 / 刷新 */
  const reloadDirs = useCallback(
    (dirs: string[]) => {
      if (!dirs.length) return Promise.resolve()
      for (const d of dirs) {
        delete cacheRef.current[d]
        delete inflightRef.current[d]
        epochRef.current[d] = (epochRef.current[d] ?? 0) + 1
      }
      setCache({ ...cacheRef.current })
      return Promise.all(dirs.map((d) => loadDir(d))).then(() => {})
    },
    [loadDir]
  )

  // 切节点:重置缓存、在途与代际,拉根切片(只取第一层,空节点据此显示扫描引导)
  useEffect(() => {
    nodeRef.current = selectedNodeId
    cacheRef.current = {}
    inflightRef.current = {}
    epochRef.current = {}
    setCache({})
    void loadDir('')
  }, [selectedNodeId, loadDir])

  // 惰性拉取:展开集里的目录按需加载(覆盖:点目录展开、首屏恢复展开集、
  // 搜索跳转/URL 直连深层自动逐层展开)
  useEffect(() => {
    for (const d of exp) void loadDir(d)
  }, [exp, loadDir])

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

  async function toggleRag(node: TreeNode | any, e: React.MouseEvent) {
    e.stopPropagation()
    if (!admin || busy) return
    const docId = (node as any).id as number | undefined
    const path = (node as any)._path as string
    if (docId === undefined || !path) return
    setBusy(true)
    try {
      const toExclude = (node as any)._rag_status !== 'excluded'
      await api.setDocumentRag(docId, toExclude)
      const parent = path.split('/').slice(0, -1).join('/')
      await reloadDirs([parent])
      toast.success(t('filetree.ragUpdated'))
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function confirmBatch() {
    if (!admin || busy || !selectMode) return
    const target = Array.from(picked.values())
    if (!target.length) return
    setBusy(true)
    try {
      await api.batchSetRag(target, selectMode === 'add')
      // 重载被勾选文档所在目录
      const parents = new Set<string>()
      for (const p of picked.keys()) {
        const seg = p.split('/')
        seg.pop()
        parents.add(seg.join('/'))
      }
      await reloadDirs(Array.from(parents))
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
      await reloadDirs(Object.keys(cacheRef.current))
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function handleRefresh() {
    if (busy) return
    setBusy(true)
    try {
      await reloadDirs(Object.keys(cacheRef.current))
    } catch (err) {
      reportError(err)
    } finally {
      setBusy(false)
    }
  }

  async function expandAll() {
    if (busy) return
    setBusy(true)
    try {
      const nodeId = nodeRef.current
      const full = await api.getDocumentTree(nodeId ?? undefined) // 缺省 dir = 一次全量
      if (nodeRef.current !== nodeId) return // 已切节点,丢弃
      const { byDir, allDirs } = decompose(full)
      cacheRef.current = byDir
      inflightRef.current = {}
      setCache(byDir)
      setExp(allDirs)
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
              if (pickable) togglePick(nodePath, (node as any).id)
              return
            }
            navigate(`/knowledge/${encodeDocPath(nodePath)}`)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              if (selectMode) {
                if (pickable) togglePick(nodePath, (node as any).id)
              } else {
                navigate(`/knowledge/${encodeDocPath(nodePath)}`)
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
                if (pickable) togglePick(nodePath, (node as any).id)
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
              onClick={(e) => toggleRag(node, e)}
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
    const dirLoaded = currentPath in cache
    const isLoading = loadingDirs.has(currentPath)
    const folderCls = ['tree__item']
    if (isExpanded) folderCls.push('tree__item--expanded')

    let childrenContent: React.ReactNode = null
    if (isExpanded && dirLoaded) {
      const dirChildren = cache[currentPath]
      const children = Object.entries(dirChildren)
        .filter(([key]) => !key.startsWith('_'))
        .sort(([a, aNode], [b, bNode]) => {
          const aIsFolder = !(aNode as any)._path
          const bIsFolder = !(bNode as any)._path
          if (aIsFolder && !bIsFolder) return -1
          if (!aIsFolder && bIsFolder) return 1
          return a.localeCompare(b)
        })
      childrenContent = (
        <div className="tree__children">
          {children.map(([childName, childNode]) =>
            renderNode(childName, childNode, currentPath)
          )}
        </div>
      )
    } else if (isExpanded && isLoading) {
      childrenContent = (
        <div className="tree__children">
          <div className="tree__loading">{t('common.loading')}</div>
        </div>
      )
    }

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
        {childrenContent}
      </div>
    )
  }

  const rootLoaded = '' in cache
  const rootChildren = rootLoaded ? cache[''] : {}

  if (!rootLoaded) {
    return (
      <div className="panel panel__body">
        <EmptyState icon={<FileIcon size={28} />} title={t('common.loading')} />
      </div>
    )
  }

  if (Object.keys(rootChildren).length === 0) {
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
        {/* 第一排:条件过滤 + 全部收起/展开 + 刷新 */}
        <div className="tree-toolbar__row">
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
          <button
            className="icon-btn icon-btn--ghost"
            onClick={() => setExp([])}
            aria-label={t('filetree.collapseAll')}
            title={t('filetree.collapseAll')}
          >
            <ChevronRightIcon size={14} />
            <ChevronRightIcon size={14} style={{ marginLeft: -6 }} />
          </button>
          <button
            className="icon-btn icon-btn--ghost"
            onClick={expandAll}
            disabled={busy}
            aria-label={t('filetree.expandAll')}
            title={t('filetree.expandAll')}
          >
            <ChevronDownIcon size={14} />
            <ChevronDownIcon size={14} style={{ marginLeft: -6 }} />
          </button>
          <button
            className="icon-btn icon-btn--ghost"
            onClick={handleRefresh}
            disabled={busy}
            aria-label={t('common.refresh')}
            title={t('common.refresh')}
          >
            <RefreshIcon size={14} />
          </button>
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
      {Object.entries(rootChildren).map(([name, node]) => renderNode(name, node))}
    </div>
  )
}