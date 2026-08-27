/**
 * AgentKnowledgeMesh API 客户端
 */

const BASE_URL = '/api'

export interface Document {
  id: number
  node_id: string
  path: string
  title: string
  hash: string
  size: number
  tags: string[]
  created_at: string
  updated_at: string
  content?: string
}

export interface Node {
  id: string
  name: string
  platform: string
  ip: string | null
  status: 'online' | 'offline'
  last_heartbeat: string | null
  created_at: string
}

export interface SearchResponse {
  query: string
  count: number
  documents: Document[]
}

export interface ScanStats {
  message: string
  created: number
  updated: number
  deleted: number
}

export interface SystemStats {
  total_documents: number
  total_size_bytes: number
  total_nodes: number
  online_nodes: number
}

/** RAG 语义搜索结果项 */
export interface RagSearchResult {
  doc_id: number
  title: string
  path: string
  node_id: string
  chunk: string
  score: number
}

/** RAG 语义搜索响应 */
export interface RagSearchResponse {
  query: string
  count: number
  results: RagSearchResult[]
}

/** RAG 上下文文档 */
export interface RagContextDoc {
  title: string
  content: string
  path: string
  node_id: string
  score: number
  matched_chunk: string
}

/** RAG 上下文响应 */
export interface RagContextResponse {
  query: string
  count: number
  documents: RagContextDoc[]
}

/** RAG 索引响应 */
export interface RagIndexResponse {
  message: string
  indexed: number
  total_chunks: number
}

/** 向量存储统计 */
export interface VectorStats {
  total_chunks: number
  error?: string
}

async function fetchJSON<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

async function postJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'POST' })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

async function deleteJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

export const api = {
  // ========== Documents ==========

  /** 获取文档列表 */
  getDocuments(nodeId?: string): Promise<Document[]> {
    const params = nodeId ? `?node_id=${nodeId}` : ''
    return fetchJSON(`${BASE_URL}/documents${params}`)
  },

  /** 获取文件树 */
  getDocumentTree(nodeId?: string): Promise<Record<string, any>> {
    const params = nodeId ? `?node_id=${nodeId}` : ''
    return fetchJSON(`${BASE_URL}/documents/tree${params}`)
  },

  /** 获取文档详情 */
  getDocument(id: number): Promise<Document> {
    return fetchJSON(`${BASE_URL}/documents/${id}`)
  },

  /** 更新文档内容 */
  updateDocument(id: number, content: string): Promise<Document> {
    return fetch(`${BASE_URL}/documents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    }).then(res => {
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
      return res.json()
    })
  },

  /** 创建新文档 */
  createDocument(path: string, title: string, content: string): Promise<Document> {
    return fetch(`${BASE_URL}/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, title, content }),
    }).then(res => {
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
      return res.json()
    })
  },

  /** 触发扫描 */
  scanDocuments(): Promise<ScanStats> {
    return postJSON(`${BASE_URL}/documents/scan`)
  },

  // ========== Search ==========

  /** 搜索文档 */
  search(query: string, limit = 20): Promise<SearchResponse> {
    return fetchJSON(`${BASE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  },

  // ========== RAG ==========

  /** RAG 语义搜索 */
  ragSearch(query: string, limit = 5, nodeId?: string): Promise<RagSearchResponse> {
    let url = `${BASE_URL}/rag/search?q=${encodeURIComponent(query)}&limit=${limit}`
    if (nodeId) url += `&node_id=${nodeId}`
    return fetchJSON(url)
  },

  /** 获取 RAG 上下文（用于 AI prompt 注入） */
  ragContext(query: string, limit = 3, nodeId?: string): Promise<RagContextResponse> {
    let url = `${BASE_URL}/rag/context?q=${encodeURIComponent(query)}&limit=${limit}`
    if (nodeId) url += `&node_id=${nodeId}`
    return fetchJSON(url)
  },

  /** 触发 RAG 全量索引 */
  ragIndex(): Promise<RagIndexResponse> {
    return postJSON(`${BASE_URL}/rag/index`)
  },

  /** 获取向量存储统计 */
  getVectorStats(): Promise<VectorStats> {
    return fetchJSON(`${BASE_URL}/rag/stats`)
  },

  // ========== Nodes ==========

  /** 获取节点列表 */
  getNodes(): Promise<Node[]> {
    return fetchJSON(`${BASE_URL}/nodes`)
  },

  /** 获取节点详情 */
  getNode(nodeId: string): Promise<Node> {
    return fetchJSON(`${BASE_URL}/nodes/${nodeId}`)
  },

  /** 获取节点文档 */
  getNodeDocuments(nodeId: string): Promise<{ node: Node; documents: Document[] }> {
    return fetchJSON(`${BASE_URL}/nodes/${nodeId}/documents`)
  },

  /** 请求节点同步 */
  syncNode(nodeId: string): Promise<{ message: string }> {
    return postJSON(`${BASE_URL}/nodes/${nodeId}/sync`)
  },

  /** 删除节点 */
  deleteNode(nodeId: string): Promise<{ message: string }> {
    return deleteJSON(`${BASE_URL}/nodes/${nodeId}`)
  },

  // ========== Stats ==========

  /** 获取系统统计 */
  getStats(): Promise<SystemStats> {
    return fetchJSON(`${BASE_URL}/stats`)
  },
}
