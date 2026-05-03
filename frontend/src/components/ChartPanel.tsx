import type { EChartsOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { TableData, VizSpec } from '../types/chart'
import { buildEChartsOption } from '../utils/buildEChartsOption'

type Props = {
  viz_spec: VizSpec | null
  table: TableData | null
  /** 对当前可视化结果的解读（如 LLM 输出） */
  viz_insight?: string | null
  /** 为 true 时：对话区分析文本流式输出中，暂不在此区域展示图表 */
  analysisPending?: boolean
  /** 点击「生成数据洞察」时触发（未传则不显示按钮，如离线 Mock） */
  onRequestInsight?: () => void | Promise<void>
  insightLoading?: boolean
}

export function ChartPanel({
  viz_spec,
  table,
  viz_insight,
  analysisPending = false,
  onRequestInsight,
  insightLoading = false,
}: Props) {
  const [panelView, setPanelView] = useState<'chart' | 'table'>('chart')

  const option = useMemo(() => {
    if (!viz_spec || !table) return null
    return buildEChartsOption(viz_spec, table)
  }, [viz_spec, table])

  const isVizTableKind = viz_spec?.chart_type === 'table'

  /** 随可视化数据变更重置视图（避免在 effect 内 setState 触发 lint） */
  const vizDataRevision = useMemo(() => {
    if (!table || !viz_spec) return ''
    const cols = table.columns.join('\u0001')
    const row0 =
      table.rows[0] !== undefined ? JSON.stringify(table.rows[0]) : ''
    return `${viz_spec.chart_type}:${table.rows.length}:${cols}:${row0}`
  }, [table, viz_spec])

  const [vizRevisionSeen, setVizRevisionSeen] = useState(vizDataRevision)
  if (vizDataRevision !== vizRevisionSeen) {
    setVizRevisionSeen(vizDataRevision)
    let next: 'chart' | 'table' = 'chart'
    if (table && viz_spec && !isVizTableKind) {
      next = option !== null ? 'chart' : 'table'
    }
    setPanelView(next)
  }

  const canRenderChart = !!(table && viz_spec && !isVizTableKind && option !== null)
  const showSwitcher = !!(table && viz_spec && !isVizTableKind)

  const insightText = viz_insight?.trim() ?? ''
  const showInsightBlock = Boolean(table)
  const truncated =
    table?.meta && typeof table.meta.truncated === 'boolean'
      ? table.meta.truncated
      : false

  if (analysisPending) {
    return (
      <section className="das-chart-panel" aria-label="可视化">
        <header className="das-panel-head das-chart-panel-head">
          <div className="das-chart-head-left">
            <h2 className="das-panel-title">可视化</h2>
            <span className="das-chart-sub muted">
              等待对话区分析说明输出完成…
            </span>
          </div>
        </header>
        <div className="das-chart-body das-chart-pending">
          <div className="das-chart-pending-inner">
            <p className="das-chart-pending-lead">
              正在流式输出：问题理解、所用数据表与字段、以及结果小结。
            </p>
            <p className="muted">
              上述说明在聊天区全部展示后，本区域将自动呈现图表或数据表。
            </p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="das-chart-panel" aria-label="可视化">
      <header className="das-panel-head das-chart-panel-head">
        <div className="das-chart-head-left">
          <h2 className="das-panel-title">可视化</h2>
          {viz_spec?.title && (
            <span className="das-chart-sub">{viz_spec.title}</span>
          )}
          {truncated ? (
            <span className="das-chart-meta muted">
              （结果已达到行数上限，展示可能被截断）
            </span>
          ) : null}
        </div>
        {showSwitcher && (
          <div className="das-view-switch" role="tablist" aria-label="图表或表格视图">
            <button
              type="button"
              role="tab"
              aria-selected={panelView === 'chart'}
              className={
                'das-view-switch-btn' + (panelView === 'chart' ? ' is-active' : '')
              }
              disabled={!canRenderChart}
              title={!canRenderChart ? '当前无法渲染图表，请使用表格视图' : undefined}
              onClick={() => setPanelView('chart')}
            >
              图表
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={panelView === 'table'}
              className={
                'das-view-switch-btn' + (panelView === 'table' ? ' is-active' : '')
              }
              onClick={() => setPanelView('table')}
            >
              表格
            </button>
          </div>
        )}
      </header>
      <div className="das-chart-body">
        {!table ? (
          <div className="das-chart-empty">
            <p>暂无图表</p>
            <p className="muted">在下方输入问题并开始分析后，将在此展示图表。</p>
          </div>
        ) : !viz_spec ? (
          <div className="das-chart-stack">
            <p className="das-chart-note">暂无图表类型，预览表格：</p>
            <TablePreview table={table} />
          </div>
        ) : isVizTableKind ? (
          <TablePreview table={table} />
        ) : panelView === 'table' ? (
          <TablePreview table={table} />
        ) : canRenderChart && option ? (
          <ChartFillHost option={option} />
        ) : (
          <div className="das-chart-empty">
            <p>当前配置无法绘图</p>
            <TablePreview table={table} compact />
          </div>
        )}
      </div>
      {showInsightBlock ? (
        <div
          className="das-chart-insight das-chart-insight-below"
          role="region"
          aria-label="数据洞察"
        >
          <div className="das-chart-insight-head">
            <span className="das-chart-insight-label">数据洞察</span>
            {onRequestInsight ? (
              <button
                type="button"
                className="das-chart-insight-btn"
                disabled={insightLoading}
                onClick={() => void onRequestInsight()}
              >
                {insightLoading
                  ? '生成中…'
                  : insightText
                    ? '重新生成'
                    : '生成数据洞察'}
              </button>
            ) : null}
          </div>
          {insightText ? (
            <p className="das-chart-insight-text">{insightText}</p>
          ) : onRequestInsight ? (
            <p className="das-chart-insight-text das-chart-insight-placeholder">
              点击上方按钮，将基于当前查询结果与业务规则生成简要洞察（需配置大模型 API）。
            </p>
          ) : (
            <p className="das-chart-insight-text das-chart-insight-placeholder">
              暂无结构化洞察摘要；详细结论请以右侧对话中的说明为准。
            </p>
          )}
        </div>
      ) : null}
    </section>
  )
}

/** 图表铺满 `.das-chart-body` 剩余区域，并在分栏/窗口尺寸变化时 resize */
function ChartFillHost({ option }: { option: EChartsOption }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<InstanceType<typeof ReactECharts>>(null)

  const resize = () => {
    chartRef.current?.getEchartsInstance()?.resize()
  }

  useEffect(() => {
    const host = hostRef.current
    if (!host || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => resize())
    ro.observe(host)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    resize()
  }, [option])

  return (
    <div ref={hostRef} className="das-echarts-host">
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: '100%', width: '100%', minHeight: 200 }}
        notMerge
        lazyUpdate={false}
        opts={{ renderer: 'canvas' }}
        onChartReady={resize}
      />
    </div>
  )
}

function TablePreview({
  table,
  compact,
}: {
  table: TableData
  compact?: boolean
}) {
  const maxRows = compact ? 5 : table.rows.length
  return (
    <div className={'das-mini-table-wrap' + (compact ? ' is-compact' : '')}>
      <table className="das-mini-table">
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.slice(0, maxRows).map((row, i) => (
            <tr key={i}>
              {table.columns.map((c) => (
                <td key={c}>{String(row[c] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
