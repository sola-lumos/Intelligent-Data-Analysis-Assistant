import { fetchJson } from './base'
import type {
  ChatRequestPayload,
  ChatResponsePayload,
} from '../types/api'

export async function postChatApi(
  body: ChatRequestPayload,
): Promise<ChatResponsePayload> {
  const res = await fetchJson<ChatResponsePayload>('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: body.session_id ?? null,
      message: body.message,
    }),
  })
  if (!res) {
    throw new Error('Unexpected empty POST /api/chat response')
  }
  return res
}
