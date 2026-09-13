import { createContext, useContext } from 'react'

interface KnowledgeCtxValue {
  /** 当前选中的节点(null 表示 Local/全量) */
  selectedNodeId: string | null
}

const KnowledgeCtx = createContext<KnowledgeCtxValue>({ selectedNodeId: null })

export const KnowledgeProvider = KnowledgeCtx.Provider

/** 读取当前知识库页选中的节点(右栏渲染器用于防御:文档不属于新节点时回占位) */
export function useSelectedNodeId(): string | null {
  return useContext(KnowledgeCtx).selectedNodeId
}