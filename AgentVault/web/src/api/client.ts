/**
 * AgentVault API 客户端
 */

const BASE_URL = '/api'

export interface Document {
  id: number
  path: string
  title: string
  hash: string
  size: number
  tags: string[]
  created_at: string
  updated_at: string
  content?: string
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

export const api = {
  /** 获取文档列表 */
  getDocuments(): Promise<Document[]> {
    return fetchJSON(`${BASE_URL}/documents`)
  },

  /** 获取文件树 */
  getDocumentTree(): Promise<Record<string, any>> {
    return fetchJSON(`${BASE_URL}/documents/tree`)
  },

  /** 获取文档详情 */
  getDocument(id: number): Promise<Document> {
    return fetchJSON(`${BASE_URL}/documents/${id}`)
  },

  /** 触发扫描 */
  scanDocuments(): Promise<ScanStats> {
    return postJSON(`${BASE_URL}/documents/scan`)
  },

  /** 搜索文档 */
  search(query: string, limit = 20): Promise<SearchResponse> {
    return fetchJSON(`${BASE_URL}/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  },

  /** 获取系统统计 */
  getStats(): Promise<SystemStats> {
    return fetchJSON(`${BASE_URL}/stats`)
  },
}
