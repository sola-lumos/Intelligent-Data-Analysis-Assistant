import { apiBase } from './base'

export type HealthPayload = {
  status: string
}

export async function fetchHealth(): Promise<HealthPayload> {
  const url = `${apiBase()}/api/health`
  const res = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  }
  return res.json()
}
