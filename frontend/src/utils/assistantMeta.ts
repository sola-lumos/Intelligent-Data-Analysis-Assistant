import type { VizSpec } from '../types/chart'

/** 后端 `assistant_meta` 中挂载的 viz_spec（与落库字段一致） */
export function vizSpecFromAssistantMeta(
  meta: Record<string, unknown> | null | undefined,
): VizSpec | null {
  if (!meta || typeof meta !== 'object') return null
  const raw = meta.viz_spec
  if (!raw || typeof raw !== 'object') return null
  const ctRaw = (raw as { chart_type?: unknown }).chart_type
  const chartType =
    typeof ctRaw === 'string' ? ctRaw.trim().toLowerCase() : ctRaw
  if (
    chartType !== 'bar' &&
    chartType !== 'line' &&
    chartType !== 'pie' &&
    chartType !== 'scatter' &&
    chartType !== 'table'
  ) {
    return null
  }
  return {
    ...(raw as Record<string, unknown>),
    chart_type: chartType,
  } as VizSpec
}
