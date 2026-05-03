/** MVP 查询案例：对齐后端医药星型表（`fact_pharma_sales`、`v_pharma_sales_enriched`、`fact_pharma_target`）；兼容视图 `sales_fact`（product_name / region / sale_date / amount）。演示数据为 2026 年 Q1，销售大区为华东、华南。 */

/** 基础：计数、产品合计、大区对比、排序 */
export const MVP_BASIC_QUERIES: string[] = [
  '销量明细表里一共有多少条记录？',
  '各产品的销售额合计是多少？',
  '华东地区、华南地区的销售额分别是多少？哪个大区更高？',
  '销售额最高的产品是哪一个？合计金额大约多少？',
  '按销售大区汇总销售额，从高到低排序。',
]

/** 分组：产品、大区、医院、代表 */
export const MVP_GROUP_STATS: string[] = [
  '按产品分组统计销售金额总和。',
  '按销售大区统计销售金额和明细条数。',
  '只看华东地区，各产品的销售额分别是多少？',
  '按医院统计销售金额，列出销售额前五的医院名称和金额。',
  '各位医药代表的销售额合计是多少？代表姓名一起列出。',
]

/** 时间：演示数据为 2026-01-01 至 2026-03-31 */
export const MVP_TIME_TREND: string[] = [
  '按月看看 2026 年第一季度的销售额变化（可以按月份汇总）。',
  '2026 年 1 月和 3 月的总销售额大概差多少？',
  '单日销售金额最高的那一天是哪天？当天总金额多少？',
]

/** 目标与达成：对应月度目标表与事实表对比 */
export const MVP_TARGET_ACHIEVEMENT: string[] = [
  '2026 年 1 月、2 月、3 月，每个销售大区的月度目标金额分别是多少？',
  '2026 年 1 月各大区的实际销售额和月度目标各是多少？能算一下达成率吗？',
  '哪条「大区 + 产品 + 月」的考核目标金额最高？把大区名、产品名、月份和金额列出来。',
]

/** 多轮 / 钻取式问法 */
export const MVP_FOLLOWUPS: string[] = [
  '先按销售大区看总销售额，再只保留华东地区继续分析。',
  '各产品销售额从高到低排名，取前三名产品及其金额。',
  '在连表后的销量明细里，按代表姓名汇总销售额。',
]

export const MVP_EMPTY_OR_HARD: string[] = [
  '查询表 not_exist_xyz 的全部数据。',
  '昨天火星上的销售额。',
]

/** 页面「查询案例」分组（不含反面教材） */
export const SAMPLE_QUERY_GROUPS: ReadonlyArray<{
  title: string
  prompts: readonly string[]
}> = [
  { title: '基础查询', prompts: MVP_BASIC_QUERIES },
  { title: '分组统计', prompts: MVP_GROUP_STATS },
  { title: '时间趋势', prompts: MVP_TIME_TREND },
  { title: '目标与达成', prompts: MVP_TARGET_ACHIEVEMENT },
  { title: '多轮追问', prompts: MVP_FOLLOWUPS },
]

/** 边界/反面示例，默认不在主界面展示 */
export const SAMPLE_EDGE_PROMPTS = MVP_EMPTY_OR_HARD
