import { getToken, setToken } from './session.ts'

export type DesiredState = 'running' | 'stopped' | 'deleted'
export type ActualState = 'pending' | 'running' | 'stopped' | 'error'
export type Role = 'viewer' | 'operator' | 'admin'

// The shapes the API returns (see app/schemas.py).
export interface Resource {
  id: string
  name: string
  image: string
  desired_state: DesiredState
  actual_state: ActualState
  created_at: string
  updated_at: string
}

export interface MetricPoint {
  collected_at: string
  cpu_percent: number // percent of one CPU core
  memory_bytes: number
}

export interface LatestMetric extends MetricPoint {
  resource_id: string
  name: string
}

export interface User {
  id: string
  username: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface AuditEvent {
  id: number
  created_at: string
  actor: string
  action: string
  target_id: string
  details: Record<string, unknown>
}

export class ApiError extends Error {
  readonly status: number
  // Seconds to wait before trying again, when the server says (429 responses).
  readonly retryAfter: number | null

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(path, { ...init, headers })
  if (response.status === 401 && token) {
    // The token expired, a password reset revoked it, or the account was
    // deactivated. Signing out shows the login screen again.
    setToken(null)
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response), retryAfter(response))
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const { detail } = await response.json()
    // FastAPI sends {"detail": "..."} for errors raised on purpose, and a list of
    // problems when a request fails validation.
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
  } catch {
    // Not JSON: fall back to the status line.
  }
  return response.statusText || `Request failed (${response.status})`
}

function retryAfter(response: Response): number | null {
  const seconds = Number(response.headers.get('Retry-After'))
  return seconds > 0 ? seconds : null
}

function sendJson(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

const resourcePath = (id: string) => `/resources/${encodeURIComponent(id)}`

export async function login(username: string, password: string): Promise<string> {
  // The OAuth2 password flow takes a form, not JSON.
  const body = new URLSearchParams({ username, password })
  const token = await request<{ access_token: string }>('/auth/token', { method: 'POST', body })
  return token.access_token
}

export const getMe = () => request<User>('/auth/me')
export const listResources = () => request<Resource[]>('/resources')
export const latestMetrics = () => request<LatestMetric[]>('/metrics/latest')
export const resourceMetrics = (id: string, minutes: number) =>
  request<MetricPoint[]>(`${resourcePath(id)}/metrics?minutes=${minutes}`)
export const listAudit = (limit: number) => request<AuditEvent[]>(`/audit?limit=${limit}`)

export const createResource = (name: string, image: string) =>
  request<Resource>('/resources', sendJson('POST', { name, image }))
export const setDesiredState = (id: string, desiredState: 'running' | 'stopped') =>
  request<Resource>(resourcePath(id), sendJson('PATCH', { desired_state: desiredState }))
export const deleteResource = (id: string) =>
  request<Resource>(resourcePath(id), { method: 'DELETE' })
