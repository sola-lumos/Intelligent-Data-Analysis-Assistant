import type { TableData } from './chart'

export type Role = 'user' | 'assistant'

/** 与后端 `GET /api/sessions` 单条记录（SessionOut）字段一致（snake_case） */
export interface SessionDTO {
  id: string
  title: string
  created_at: number
  updated_at: number
}

/**
 * 与后端 `GET /api/sessions/{id}/messages`（MessageOut）一致；
 * `GET .../messages` 无顶层 `table` 字段：若助手落库时在 `assistant_meta.table` 中保存预览数据，前端会填入 `ChatThreadMessage.table`。
 */
export interface ChatThreadMessage {
  id: string
  session_id?: string
  role: Role
  content: string
  sql_text?: string | null
  assistant_meta?: Record<string, unknown> | null
  created_at?: number
  table?: TableData | null
  /** 与 `assistant_meta.viz_insight` 同步；落库后刷新会话仍可从 meta 恢复 */
  viz_insight?: string | null
}
