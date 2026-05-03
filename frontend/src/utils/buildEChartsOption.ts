import type { EChartsOption } from 'echarts'
import type { TableData, VizSpec } from '../types/chart'

function pickNum(v: unknown): number {
  if (typeof v === 'number' && !Number.isNaN(v)) return v
  if (typeof v === 'string') {
    const n = Number(v)
    return Number.isNaN(n) ? 0 : n
  }
  return 0
}

function pickStr(v: unknown): string {
  return v == null ? '' : String(v)
}

/** 折线/柱状数据点标签：可读数字，避免过长小数 */
function formatDataLabel(n: number): string {
  if (!Number.isFinite(n)) return ''
  const abs = Math.abs(n)
  if (abs >= 1e7) return n.toExponential(2)
  const rounded = Math.round(n * 100) / 100
  if (Number.isInteger(rounded)) return String(rounded)
  return String(rounded)
}

export function buildEChartsOption(
  spec: VizSpec,
  table: TableData,
): EChartsOption | null {
  const { chart_type, title, x_field, y_field, category_field, value_field } =
    spec
  const rows = table.rows

  if (chart_type === 'table' || rows.length === 0) {
    return null
  }

  if (chart_type === 'bar' || chart_type === 'line') {
    const xKey = x_field ?? table.columns[0]
    const yKey = y_field ?? table.columns[1]
    if (!xKey || !yKey) return null
    const x =
      xKey === yKey && rows.length
        ? rows.map((_, i) =>
            rows.length === 1 ? '结果' : `样本 ${i + 1}`,
          )
        : rows.map((r) => pickStr(r[xKey]))
    const y = rows.map((r) => pickNum(r[yKey]))
    const pointLabel = {
      show: true,
      position: 'top' as const,
      distance: chart_type === 'line' ? 6 : 4,
      fontSize: 11,
      color: '#334155',
      formatter: (p: { value: unknown }) => formatDataLabel(pickNum(p.value)),
    }
    return {
      title: title ? { text: title, left: 'center' } : undefined,
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: unknown) => formatDataLabel(pickNum(v)),
      },
      grid: {
        left: 48,
        right: 24,
        top: title ? 56 : 36,
        bottom: 40,
      },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: x.length > 6 ? 30 : 0 } },
      yAxis: { type: 'value' },
      series: [
        {
          type: chart_type,
          data: y,
          name: yKey,
          label: pointLabel,
          emphasis: { focus: 'series' },
        },
      ],
    }
  }

  if (chart_type === 'pie') {
    const nameKey = category_field ?? x_field ?? table.columns[0]
    const valKey = value_field ?? y_field ?? table.columns[1]
    if (!nameKey || !valKey) return null
    const data = rows.map((r) => ({
      name: pickStr(r[nameKey]),
      value: pickNum(r[valKey]),
    }))
    return {
      title: title ? { text: title, left: 'center' } : undefined,
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      series: [
        {
          type: 'pie',
          radius: '58%',
          data,
          label: {
            show: true,
            formatter: '{b}\n{d}%',
            fontSize: 11,
            color: '#334155',
          },
          labelLine: { show: true, length: 12, length2: 8 },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0,0,0,0.2)',
            },
          },
        },
      ],
    }
  }

  if (chart_type === 'scatter') {
    const xKey = x_field ?? table.columns[0]
    const yKey = y_field ?? table.columns[1]
    if (!xKey || !yKey) return null
    const data = rows.map((r) => [pickNum(r[xKey]), pickNum(r[yKey])] as [number, number])
    return {
      title: title ? { text: title, left: 'center' } : undefined,
      tooltip: { trigger: 'item' },
      grid: { left: 48, right: 24, top: title ? 48 : 24, bottom: 40 },
      xAxis: { type: 'value', name: xKey },
      yAxis: { type: 'value', name: yKey },
      series: [{ type: 'scatter', data }],
    }
  }

  return null
}
