/** API 基础地址与 JSON fetch（契约与后端 FastAPI snake_case JSON 对齐） */

export function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL ?? ''
  return raw.endsWith('/') ? raw.slice(0, -1) : raw
}

function mergeHeaders(init?: RequestInit): HeadersInit {
  const h = new Headers(init?.headers ?? undefined)
  if (!h.has('Accept')) {
    h.set('Accept', 'application/json')
  }
  return h
}

export async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T | null> {
  const slash = path.startsWith('/') ? path : `/${path}`
  const url = `${apiBase()}${slash}`
  const res = await fetch(url, { ...init, headers: mergeHeaders(init) })
  if (res.status === 204) {
    return null
  }
  const text = await res.text()
  if (!res.ok) {
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (!text.trim()) {
    return null
  }
  return JSON.parse(text) as T
}
