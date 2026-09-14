/**
 * AgentKnowledgeMesh API 客户端
 */

import i18n from '../i18n'
const BASE_URL = '/api'

export interface Document {
  id: number
  node_id: string
  path: string
  title: string
  hash: string
  size: number
  tags: string[]
  rag_status?: 'indexed' | 'pending' | 'excluded'
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
  disabled?: boolean
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

// ========== Auth(account-auth)==========

export interface AuthSession {
  token: string
  username: string
  role: 'admin' | 'viewer'
}

const AUTH_KEY = 'akm.auth'

/** 读取当前登录会话 */
export function getSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? (JSON.parse(raw) as AuthSession) : null
  } catch {
    return null
  }
}

/** 写入/清除登录会话 */
export function setSession(session: AuthSession | null): void {
  try {
    if (session) localStorage.setItem(AUTH_KEY, JSON.stringify(session))
    else localStorage.removeItem(AUTH_KEY)
  } catch {
    /* 存储不可用时忽略 */
  }
}

/** 当前用户是否管理员 */
export function isAdmin(): boolean {
  return getSession()?.role === 'admin'
}

/** 组装鉴权请求头 */
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const session = getSession()
  const headers = { ...extra }
  if (session?.token) headers['Authorization'] = `Bearer ${session.token}`
  return headers
}

/** 401:清除会话并广播,由 App 层切回登录页 */
function handleUnauthorized(): void {
  setSession(null)
  window.dispatchEvent(new CustomEvent('akm:unauthorized'))
}

async function fetchJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: authHeaders() })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error(i18n.t('auth.sessionExpired'))
  }
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

async function postJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'POST', headers: authHeaders() })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error(i18n.t('auth.sessionExpired'))
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}

async function deleteJSON<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'DELETE', headers: authHeaders() })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error(i18n.t('auth.sessionExpired'))
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/** 登录(account-auth) */
export async function login(username: string, password: string): Promise<AuthSession> {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || i18n.t('login.error'))
  }
  const data = await response.json()
  const session: AuthSession = {
    token: data.access_token,
    username: data.username,
    role: data.role === 'admin' ? 'admin' : 'viewer',
  }
  setSession(session)
  return session
}

/** 退出登录 */
export function logout(): void {
  setSession(null)
}

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  role: 'admin' | 'viewer'
  disabled: boolean
  created_at: string | null
}

/** API Token 信息(脱敏) */
export interface ApiTokenInfo {
  id: number
  name: string
  token_prefix: string
  role: 'admin' | 'viewer'
  created_by: string | null
  created_at: string | null
  last_used_at: string | null
  revoked: boolean
}

/** 携带 JSON body 的 POST */
async function postJSONBody<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error(i18n.t('auth.sessionExpired'))
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/** 携带 JSON body 的 PUT */
async function putJSONBody<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (response.status === 401) {
    handleUnauthorized()
    throw new Error(i18n.t('auth.sessionExpired'))
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}

export const api = {
  // ========== Documents ==========

  /** 获取文档列表(可指定节点或按 RAG 状态过滤) */
  getDocuments(nodeId?: string, ragStatus?: string): Promise<Document[]> {
    const params = new URLSearchParams()
    if (nodeId) params.set('node_id', nodeId)
    if (ragStatus) params.set('rag_status', ragStatus)
    const qs = params.toString()
    return fetchJSON(`${BASE_URL}/documents${qs ? `?${qs}` : ''}`)
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
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ content }),
    }).then(res => {
      if (res.status === 401) { handleUnauthorized(); throw new Error(i18n.t('auth.sessionExpired')) }
      if (res.status === 403) throw new Error(i18n.t('auth.forbidden'))
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
      return res.json()
    })
  },

  /** 创建新文档 */
  createDocument(path: string, title: string, content: string): Promise<Document> {
    return fetch(`${BASE_URL}/documents`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ path, title, content }),
    }).then(res => {
      if (res.status === 401) { handleUnauthorized(); throw new Error(i18n.t('auth.sessionExpired')) }
      if (res.status === 403) throw new Error(i18n.t('auth.forbidden'))
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

  /** 设置全局 RAG 同步模式(auto/manual,admin) */
  setRagMode(mode: 'auto' | 'manual'): Promise<{ rag_sync_mode: string }> {
    return putJSONBody(`${BASE_URL}/settings`, { rag_sync_mode: mode })
  },

  /** 读取全局设置 */
  getSettings(): Promise<{ rag_sync_mode: 'auto' | 'manual' }> {
    return fetchJSON(`${BASE_URL}/settings`)
  },

  /** 单篇加入/移出 RAG(admin) */
  setDocumentRag(id: number, enabled: boolean): Promise<Document> {
    return putJSONBody(`${BASE_URL}/documents/${id}/rag`, { enabled })
  },

  /** 批量加入/移出 RAG(admin) */
  batchSetRag(docIds: number[], enabled: boolean): Promise<{ updated: number }> {
    return postJSONBody(`${BASE_URL}/documents/rag/batch`, { doc_ids: docIds, enabled })
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

  /** 禁用/启用节点(admin) */
  setNodeDisabled(nodeId: string, disabled: boolean): Promise<Node> {
    return fetch(`${BASE_URL}/nodes/${nodeId}`, {
      method: 'PUT',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ disabled }),
    }).then(res => {
      if (res.status === 401) { handleUnauthorized(); throw new Error(i18n.t('auth.sessionExpired')) }
      if (res.status === 403) throw new Error(i18n.t('auth.forbidden'))
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
      return res.json()
    })
  },

  /** 重置节点 token(admin),明文仅本次返回 */
  resetNodeToken(nodeId: string): Promise<{ node_id: string; node_token: string }> {
    return postJSONBody(`${BASE_URL}/nodes/${nodeId}/reset-token`, {})
  },

  // ========== Stats ==========

  /** 获取系统统计 */
  getStats(): Promise<SystemStats> {
    return fetchJSON(`${BASE_URL}/stats`)
  },

  // ========== Auth 管理(admin)==========

  /** 用户列表 */
  getUsers(): Promise<UserInfo[]> {
    return fetchJSON(`${BASE_URL}/auth/users`)
  },

  /** 创建用户 */
  createUser(username: string, password: string, role: 'admin' | 'viewer'): Promise<UserInfo> {
    return postJSONBody(`${BASE_URL}/auth/users`, { username, password, role })
  },

  /** 更新用户:停用/启用、改角色、重置密码(仅传需要改的字段) */
  updateUser(
    userId: number,
    patch: { disabled?: boolean; role?: 'admin' | 'viewer'; password?: string }
  ): Promise<UserInfo> {
    return putJSONBody(`${BASE_URL}/auth/users/${userId}`, patch)
  },

  /** 删除用户 */
  deleteUser(userId: number): Promise<{ message: string }> {
    return deleteJSON(`${BASE_URL}/auth/users/${userId}`)
  },

  /** API Token 列表(脱敏) */
  getApiTokens(): Promise<ApiTokenInfo[]> {
    return fetchJSON(`${BASE_URL}/auth/tokens`)
  },

  /** 创建 API Token(明文仅本次返回) */
  createApiToken(name: string, role: 'admin' | 'viewer'): Promise<ApiTokenInfo & { token: string }> {
    return postJSONBody(`${BASE_URL}/auth/tokens`, { name, role })
  },

  /** 吊销 API Token */
  revokeApiToken(tokenId: number): Promise<{ message: string }> {
    return deleteJSON(`${BASE_URL}/auth/tokens/${tokenId}`)
  },

  /** 彻底删除已吊销的 API Token(不可恢复) */
  purgeApiToken(tokenId: number): Promise<{ message: string }> {
    return deleteJSON(`${BASE_URL}/auth/tokens/${tokenId}/purge`)
  },
}
