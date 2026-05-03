/** `POST /api/chat/stream`：SSE §4.6 主方案；默认不重试以避免重复写入会话 */

import { apiBase } from './base'
import type { ChatRequestPayload } from '../types/api'
import type { TableData, VizSpec } from '../types/chart'

export type ChatStreamHandlers = {
  onAnswer?: (payload: { content?: string }) => void
  onSql?: (payload: { sql?: string }) => void
  onTable?: (payload: TableData) => void
  onChart?: (payload: { viz_spec: VizSpec }) => void
  onInsight?: (payload: { viz_insight?: string | null }) => void
  onDone?: (payload: {
    session_id: string
    message_id: string
    viz_insight?: string | null
  }) => void
  onError?: (payload: { message?: string; code?: string }) => void
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

/** 解析单行块中的 event/data（标准 SSE） */
function handleSseBlock(
  blockRaw: string,
  handlers: ChatStreamHandlers,
): 'error' | 'done' | null {
  let eventName = ''
  const dataParts: string[] = []
  for (const rawLine of blockRaw.split(/\n/)) {
    const line = rawLine.replace(/\r$/, '')
    if (!line) continue
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataParts.push(line.slice('data:'.length).trimStart())
    }
  }
  const dataJoined = dataParts.join('\n')
  let payload: unknown = {}
  if (dataJoined) {
    try {
      payload = JSON.parse(dataJoined) as unknown
    } catch {
      payload = { raw: dataJoined }
    }
  }
  const pObj = typeof payload === 'object' && payload !== null ? payload : {}
  const kind = eventName || ''

  switch (kind) {
    case 'answer':
      handlers.onAnswer?.(pObj as { content?: string })
      break
    case 'sql':
      handlers.onSql?.(pObj as { sql?: string })
      break
    case 'table':
      handlers.onTable?.(pObj as TableData)
      break
    case 'chart':
      handlers.onChart?.(pObj as { viz_spec: VizSpec })
      break
    case 'insight':
      handlers.onInsight?.(pObj as { viz_insight?: string | null })
      break
    case 'done':
      handlers.onDone?.(
        pObj as {
          session_id: string
          message_id: string
          viz_insight?: string | null
        },
      )
      return 'done'
    case 'error':
      handlers.onError?.(pObj as { message?: string; code?: string })
      return 'error'
    default:
      if (kind) break
      {
        const o = pObj as Record<string, unknown>
        const hasTableShape =
          Array.isArray(o.columns) &&
          Array.isArray(o.rows) &&
          !(
            typeof o.viz_spec === 'object' &&
            o.viz_spec !== null &&
            !Array.isArray(o.viz_spec)
          )
        if (hasTableShape) {
          handlers.onTable?.(pObj as TableData)
          break
        }
        if (
          typeof o.viz_spec === 'object' &&
          o.viz_spec !== null &&
          !Array.isArray(o.viz_spec)
        ) {
          handlers.onChart?.({ viz_spec: o.viz_spec as VizSpec })
        }
      }
      break
  }
  return null
}

async function consumeSseOnce(
  body: ChatRequestPayload,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const url = `${apiBase()}/api/chat/stream`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: body.session_id ?? undefined,
      message: body.message,
    }),
    signal,
  })

  if (!res.ok) {
    const txt = await res.text()
    handlers.onError?.({
      message: txt || `HTTP ${res.status}`,
      code: 'http_error',
    })
    throw new Error(txt || `HTTP ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('无响应正文（ReadableStream）')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      for (;;) {
        const ix = buffer.indexOf('\n\n')
        if (ix < 0) break
        const block = buffer.slice(0, ix)
        buffer = buffer.slice(ix + 2)
        const outcome = handleSseBlock(block, handlers)
        if (outcome === 'error') {
          throw new Error('stream_error_event')
        }
        if (outcome === 'done') return
      }
    }

    const tailFlush = decoder.decode()
    buffer += tailFlush
    const rest = buffer.trim()
    if (rest) {
      const outcome = handleSseBlock(rest, handlers)
      if (outcome === 'error') throw new Error('stream_error_event')
      if (outcome === 'done') return
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * POST `/api/chat/stream`，消费 SSE；可选重试。**注意**：服务端每次请求都会落库用户消息，`maxRetries` &gt; 0 可能造成重复会话轮次，默认为 0。
 */
export async function postChatStream(
  body: ChatRequestPayload,
  handlers: ChatStreamHandlers,
  options?: { signal?: AbortSignal; maxRetries?: number },
): Promise<void> {
  const maxRetries = options?.maxRetries ?? 0
  let lastErr: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (attempt > 0) await sleep(360 * attempt)
    try {
      await consumeSseOnce(body, handlers, options?.signal)
      return
    } catch (e) {
      lastErr = e
      if (options?.signal?.aborted) throw e
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr))
}
