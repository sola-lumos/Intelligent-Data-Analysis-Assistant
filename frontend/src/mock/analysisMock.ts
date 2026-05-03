import type { TableData, VizSpec } from '../types/chart'
import type { ChatResponsePayload } from '../types/api'

/** 与线上一致：助手正文仅为简短结论文本（不含「查询结果」等追加区块）；SQL 仍单独下发 */
function mockAnswerBody(intro: string): string {
  return intro.trim()
}

/** 与设计文档示例一致：`sql`、`table`、`viz_spec` 与后端 `POST /api/chat` 对齐 */
export function mockAnalysisReply(userText: string): Pick<
  ChatResponsePayload,
  'answer' | 'sql' | 'table' | 'viz_spec'
> & {
  viz_insight: string
} {
  const trimmed = userText.trim()
  const table: TableData = {
    columns: ['product_name', 'sales_amount'],
    rows: [
      { product_name: 'A产品', sales_amount: 12000 },
      { product_name: 'B产品', sales_amount: 8000 },
      { product_name: 'C产品', sales_amount: 5500 },
    ],
  }
  const viz_spec: VizSpec = {
    chart_type: 'bar',
    title: '产品销售额对比',
    x_field: 'product_name',
    y_field: 'sales_amount',
  }

  if (/饼|占比/.test(trimmed)) {
    const sql =
      'SELECT product_name, SUM(amount) AS sales_amount FROM sales GROUP BY product_name'
    return {
      answer: mockAnswerBody('按产品看销售额占比：A 档领先，B、C 次之。'),
      sql,
      table,
      viz_spec: {
        chart_type: 'pie',
        title: '销售额占比',
        category_field: 'product_name',
        value_field: 'sales_amount',
      },
      viz_insight:
        '饼图侧重占比：三档差距明显（约 43% / 29% / 20%）；若只看绝对额，柱状图更合适。',
    }
  }

  if (/折线|趋势|月/.test(trimmed)) {
    const lineTable: TableData = {
      columns: ['month', 'sales_amount'],
      rows: [
        { month: '1月', sales_amount: 4200 },
        { month: '2月', sales_amount: 5100 },
        { month: '3月', sales_amount: 4800 },
        { month: '4月', sales_amount: 6200 },
      ],
    }
    const sql =
      'SELECT strftime("%m", sale_date) AS month, SUM(amount) AS sales_amount FROM sales GROUP BY month'
    return {
      answer: mockAnswerBody('近几个月销售额波动上升，4 月最高。'),
      sql,
      table: lineTable,
      viz_spec: {
        chart_type: 'line',
        title: '月度销售额趋势',
        x_field: 'month',
        y_field: 'sales_amount',
      },
      viz_insight:
        '折线捕捉「时间先后」为主：整体上行，局部在 4 月出现尖峰；注意月份是否按日历序而非字典序。',
    }
  }

  const sql =
    'SELECT product_name, SUM(amount) AS sales_amount FROM sales GROUP BY product_name ORDER BY sales_amount DESC'
  return {
    answer: mockAnswerBody(
      `已对「${trimmed.slice(0, 40)}${trimmed.length > 40 ? '…' : ''}」生成示例结果（Mock）。`,
    ),
    sql,
    table,
    viz_spec,
    viz_insight:
      '柱状图适合类目对比：A 产品明显高于 B、C，尾部差距约 3700～6500（相对值）；可作库存或投放优先级参考。',
  }
}
