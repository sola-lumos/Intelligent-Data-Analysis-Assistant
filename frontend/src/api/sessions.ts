import { apiBase, fetchJson } from './base'
import type {
  MessageOutDTO,
  SessionCreatePayload,
  SessionOutDTO,
  SessionPatchPayload,
} from '../types/api'

export async function listSessionsApi(): Promise<SessionOutDTO[]> {
  const res = await fetchJson<SessionOutDTO[]>('/api/sessions', {
    method: 'GET',
  })
  return res ?? []
}

export async function createSessionApi(
  body: SessionCreatePayload = {},
): Promise<SessionOutDTO> {
  const res = await fetchJson<SessionOutDTO>('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res) throw new Error('Unexpected empty POST /api/sessions')
  return res
}

export async function patchSessionApi(
  sessionId: string,
  body: SessionPatchPayload,
): Promise<SessionOutDTO> {
  const res = await fetchJson<SessionOutDTO>(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
  if (!res) throw new Error('Unexpected empty PATCH /api/sessions')
  return res
}

export async function deleteSessionApi(sessionId: string): Promise<void> {
  const url = `${apiBase()}/api/sessions/${encodeURIComponent(sessionId)}`
  const res = await fetch(url, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(await res.text())
  }
}

export async function listMessagesApi(sessionId: string): Promise<MessageOutDTO[]> {
  const res = await fetchJson<MessageOutDTO[]>(
    `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
    { method: 'GET' },
  )
  return res ?? []
}

export type VizInsightResponse = { viz_insight: string }

/** 按需生成某条助手消息的数据洞察（落库并返回正文） */
export async function postMessageInsightApi(
  sessionId: string,
  messageId: string,
): Promise<VizInsightResponse> {
  const res = await fetchJson<VizInsightResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/insight`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    },
  )
  if (!res?.viz_insight) {
    throw new Error('Unexpected empty insight response')
  }
  return res
}
