/** What every Month by month card needs, worked out once by Overview.svelte. */
import type { Filters } from '../../lib/filtering'
import { monthLabel, type Lens, type Row } from '../../lib/overview/shaping'

export interface OverviewContext {
  /** Rows after the filters. */
  rows: Row[]
  months: string[]
  selected: string
  previous: string
  isPartial: boolean
  asOfDay: number
  lens: Lens
  /** The first month logged in full (comparisons start there). */
  since: string | null
  /** Whether last month was logged in full, so a ▲/▼ is fair. */
  comparable: boolean
  /** The day logging began last month, when it was logged only in part. */
  partly: number | null
  /** The month logging began in, when it began after its 7th (marked with *). */
  partlyMonth: string | null
  firstDate: string | null
  /** "Sep 26" or "Sep 26 (days 1–10)" while the month is going. */
  previousTitle: string
  headline: string
  noun: string
  filters: Filters
}

/** A KPI's sparkbars: one per month, the picked one green, a month in progress faded. */
export function sparkBars(values: Map<string, number>, ctx: Pick<OverviewContext, 'selected' | 'isPartial'>,
  format: (v: number) => string) {
  return [...values.entries()].map(([m, v]) => ({
    label: monthLabel(m, true).slice(0, 3),
    value: v,
    title: `${monthLabel(m)}: ${format(v)}${m === ctx.selected && ctx.isPartial ? ' so far' : ''}`,
    picked: m === ctx.selected,
    partial: m === ctx.selected && ctx.isPartial,
  }))
}
