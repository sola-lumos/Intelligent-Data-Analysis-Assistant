/** 与设计文档 §4 snake_case 一致（Phase 2 Mock） */

export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'table'

export interface VizSpec {
  chart_type: ChartType
  title?: string
  x_field?: string
  y_field?: string
  category_field?: string
  value_field?: string
}

export interface TableData {
  columns: string[]
  rows: Record<string, unknown>[]
  /** 与后端对齐，例如 `{ truncated: true }`（触达 LIMIT 上限） */
  meta?: Record<string, unknown>
}
