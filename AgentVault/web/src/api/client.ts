/**
 * AgentVault API 客户端
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

  /** 触发扫描 */
  scanDocuments(): Promise<ScanStats> {
    return postJSON(`${BASE_URL}/documents/scan`)
  },

  // ========== Search ==========

  /** 搜索文档 */
  search(query: string, limit = 20): Promise<SearchResponse> {
    return fetchJSON(`${BASE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`)
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
