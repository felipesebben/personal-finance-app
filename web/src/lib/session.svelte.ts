/**
 * The login session, the toast after a save, and the API client.
 *
 * The session is an inactivity timeout: the API's token lasts
 * ACCESS_TOKEN_EXPIRE_MINUTES, and keepAlive() swaps it for a fresh one
 * (POST /token/refresh) whenever the app is used and the token is more than
 * RENEW_AFTER_MS old. Any 401 means it has expired: endSession() forgets the
 * token and the login form says why, once.
 *
 * The token is kept in localStorage so reopening the app on a phone within
 * the timeout doesn't ask for the password again.
 *
 * GETs are cached for CACHE_MS per path; every write clears the cache, so
 * the next read is fresh (the Streamlit app's st.cache_data.clear()).
 */
const STORE_KEY = 'hf-session'
export const RENEW_AFTER_MS = 5 * 60 * 1000
const CACHE_MS = 60 * 1000
export const EXPIRED_MESSAGE = "You were logged out because the app wasn't used for a while. Please log in again."

/** Where the API lives: same origin, under /api (Vite's proxy in dev, nginx in Docker). */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

interface Stored {
  token: string
  email: string
  renewedAt: number
}

function load(): Stored | null {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    return raw ? (JSON.parse(raw) as Stored) : null
  } catch {
    return null
  }
}

function save(s: Stored | null) {
  try {
    if (s) localStorage.setItem(STORE_KEY, JSON.stringify(s))
    else localStorage.removeItem(STORE_KEY)
  } catch {
    /* private mode: the session lives only in memory */
  }
}

const initial = load()

export const session = $state({
  token: initial?.token ?? (null as string | null),
  email: initial?.email ?? '',
  renewedAt: initial?.renewedAt ?? 0,
  logoutMessage: '' as string,
  /** Bumped on every write, so views refetch. */
  version: 0,
})

export const toast = $state({ message: '', tone: 'ok' as 'ok' | 'error', id: 0 })

export function showToast(message: string, tone: 'ok' | 'error' = 'ok') {
  toast.message = message
  toast.tone = tone
  toast.id += 1
}

const cache = new Map<string, { at: number; data: unknown }>()

export function clearCache() {
  cache.clear()
}

export function startSession(token: string, email: string) {
  session.token = token
  session.email = email.trim()
  session.renewedAt = Date.now()
  session.logoutMessage = ''
  clearCache()
  save({ token, email: session.email, renewedAt: session.renewedAt })
}

export function endSession(message: string | null = EXPIRED_MESSAGE) {
  session.token = null
  session.email = ''
  session.renewedAt = 0
  session.logoutMessage = message ?? ''
  clearCache()
  save(null)
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? (typeof detail === 'string' ? detail : `Request failed (${status})`))
    this.status = status
    this.detail = detail
  }
}

function headers(json: boolean): HeadersInit {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  if (session.token) h.Authorization = `Bearer ${session.token}`
  return h
}

async function readError(response: Response): Promise<ApiError> {
  let detail: unknown = null
  try {
    const body = await response.json()
    detail = body?.detail ?? body
  } catch {
    /* not JSON */
  }
  let message: string | undefined
  if (typeof detail === 'string') message = detail
  else if (Array.isArray(detail)) message = detail.map((d) => d?.msg ?? String(d)).join('; ')
  else if (detail && typeof detail === 'object' && 'message' in detail) message = String((detail as { message: unknown }).message)
  return new ApiError(response.status, detail, message)
}

async function send(method: string, path: string, body?: unknown, form = false): Promise<Response> {
  const url = `${API_BASE}/${path.replace(/^\//, '')}`
  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: form ? { ...(session.token ? { Authorization: `Bearer ${session.token}` } : {}) } : headers(body !== undefined),
      body: form ? (body as URLSearchParams) : body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, null, 'Could not reach the app server. Is it running?')
  }
  if (response.status === 401 && session.token) {
    endSession()
    throw new ApiError(401, null, 'Your session has expired.')
  }
  return response
}

/** Renews the token when it's older than RENEW_AFTER_MS; a 401 ends the session. */
export async function keepAlive(): Promise<void> {
  if (!session.token) return
  if (Date.now() - session.renewedAt < RENEW_AFTER_MS) return
  session.renewedAt = Date.now() // one renewal at a time
  try {
    const response = await send('POST', 'token/refresh')
    if (response.ok) {
      const data = await response.json()
      if (data?.access_token) {
        session.token = data.access_token
        session.renewedAt = Date.now()
        save({ token: data.access_token, email: session.email, renewedAt: session.renewedAt })
      }
    }
  } catch {
    /* try again on the next use */
  }
}

/** GET, cached per path for a minute. Throws ApiError on failure. */
export async function get<T>(path: string, { fresh = false } = {}): Promise<T> {
  void keepAlive()
  const hit = cache.get(path)
  if (!fresh && hit && Date.now() - hit.at < CACHE_MS) return hit.data as T
  const response = await send('GET', path)
  if (!response.ok) throw await readError(response)
  const data = (await response.json()) as T
  cache.set(path, { at: Date.now(), data })
  return data
}

async function write<T>(method: string, path: string, body?: unknown): Promise<T> {
  void keepAlive()
  const response = await send(method, path, body)
  if (!response.ok) throw await readError(response)
  clearCache()
  session.version += 1
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const post = <T = unknown>(path: string, body?: unknown) => write<T>('POST', path, body)
export const put = <T = unknown>(path: string, body?: unknown) => write<T>('PUT', path, body)
export const patch = <T = unknown>(path: string, body?: unknown) => write<T>('PATCH', path, body)
export const del = <T = unknown>(path: string) => write<T>('DELETE', path)

/** Logs in with the OAuth2 form the API expects; returns an error message or null. */
export async function login(email: string, password: string): Promise<string | null> {
  const form = new URLSearchParams({ username: email, password })
  try {
    const response = await send('POST', 'token', form, true)
    if (!response.ok) return 'Invalid email or password.'
    const data = await response.json()
    startSession(data.access_token, email)
    return null
  } catch (e) {
    return e instanceof Error ? e.message : 'Could not log in.'
  }
}
