import { createContext, useContext } from 'react'

interface KnowledgeCtxValue {
  /** 当前选中的节点(null=全部(所有节点+hub 本机);'local'=hub 端配置目录) */
  selectedNodeId: string | null
  /** Tree pane 是否展开 */
  treeVisible: boolean
  /** 切换 tree pane 显隐 */
  toggleTree: () => void
}

const KnowledgeCtx = createContext<KnowledgeCtxValue>({
  selectedNodeId: null,
  treeVisible: true,
  toggleTree: () => {},
})

export const KnowledgeProvider = KnowledgeCtx.Provider

/** 读取当前知识库页选中的节点(右栏渲染器用于防御:文档不属于新节点时回占位) */
export function useSelectedNodeId(): string | null {
  return useContext(KnowledgeCtx).selectedNodeId
}

/** 读取/切换 tree pane 显隐 */
export function useTreeVisible() {
  return useContext(KnowledgeCtx).treeVisible
}
export function useToggleTree() {
  return useContext(KnowledgeCtx).toggleTree
}