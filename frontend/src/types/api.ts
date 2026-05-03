/**
 * 后端 JSON 契约（与 `app/schemas` 一致）。
 * POST / PUT / PATCH 的请求体必须使用以下字段名，勿用 camelCase。
 */

import type { TableData, VizSpec } from './chart'

export type ChatRequestPayload = {
  session_id?: string | null
  message: string
}

export type ChatResponsePayload = {
  session_id: string
  message_id: string
  answer: string
  sql?: string | null
  table: TableData
  viz_spec: VizSpec
  /** 数据洞察（纯文本）；可能与 assistant_meta.viz_insight 同步 */
  viz_insight?: string | null
}

export type SessionCreatePayload = {
  title?: string
}

export type SessionPatchPayload = {
  title: string
}

export type SessionOutDTO = {
  id: string
  title: string
  created_at: number
  updated_at: number
}

export type MessageOutDTO = {
  id: string
  session_id: string
  role: string
  content: string
  sql_text?: string | null
  assistant_meta?: Record<string, unknown> | null
  created_at: number
}
