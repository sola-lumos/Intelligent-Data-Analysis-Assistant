import type { TableData } from '../types/chart'

/** 将未知 JSON 规整为图表可用的 `TableData`，非法则返回 `null`。 */
export function coerceTable(raw: unknown): TableData | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const o = raw as Record<string, unknown>
  if (!Array.isArray(o.columns) || !Array.isArray(o.rows)) return null
  return {
    columns: o.columns.map((c) => String(c)),
    rows: o.rows as Record<string, unknown>[],
    meta:
      typeof o.meta === 'object' && o.meta !== null && !Array.isArray(o.meta)
        ? (o.meta as Record<string, unknown>)
        : undefined,
  }
}

export function assistantTablePayload(
  m: { table?: TableData | null; assistant_meta?: Record<string, unknown> | null },
): TableData | null {
  const direct = coerceTable(m.table ?? null)
  if (direct) return direct
  const meta = m.assistant_meta
  if (!meta || typeof meta !== 'object') return null
  return coerceTable((meta as Record<string, unknown>).table)
}
