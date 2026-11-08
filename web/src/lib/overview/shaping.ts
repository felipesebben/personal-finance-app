/**
 * Shaping /analytics/shared and /analytics/personal responses for Month by
 * month (the Overview) and the Monthly recap. Pure, no Svelte: tested in
 * shaping.test.ts and control.test.ts. Port of the Streamlit frontend's
 * analytics_shaping.py.
 *
 * Amounts arrive as decimal strings and become integer cents here, so sums
 * are exact. Two lenses on the same expenses: "household" (the full price)
 * and "mine" (the caller's share_amount). A month in progress is compared
 * with the same days of other months through the *_to_day amounts.
 * A "pct" with nothing to compare with is null (pandas' NaN).
 */
import { addMonths, ordinal } from '../dates'
import { formatBrl, signedBrl } from '../money'
import { cents } from '../money'
import { delta } from '../delta'

export type Lens = 'Household' | 'My share'
export type Amount = 'household' | 'mine' | 'household_to_day' | 'mine_to_day'

export interface ApiRow {
  month: string
  primary_category: string
  sub_category: string | null
  cost_type: string | null
  nature?: string | null
  household: string | number
  mine: string | number
  household_to_day: string | number
  mine_to_day: string | number
  count: number
  source?: string
}

export interface Payload {
  month: string
  months: string[]
  is_partial: boolean
  as_of_day: number
  rows: ApiRow[]
  first_date?: string | null
}

/** One row with cents. */
export interface Row {
  month: string
  primary_category: string
  sub_category: string
  cost_type: string
  nature: string
  household: number
  mine: number
  household_to_day: number
  mine_to_day: number
  count: number
  source: string
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const shiftMonth = addMonths

/** '2026-10' → 'Oct 2026', or 'Oct 26' when short. */
export function monthLabel(month: string, short = false): string {
  const name = MONTH_NAMES[Number(month.slice(5, 7)) - 1]
  return short ? `${name} ${month.slice(2, 4)}` : `${name} ${month.slice(0, 4)}`
}

/** The last n months ending at `current`, newest first (for a picker). */
export function monthOptions(current: string, n = 12): string[] {
  return Array.from({ length: n }, (_, k) => shiftMonth(current, -k))
}

/** The response's rows with cents (none for a missing payload). */
export function toRows(payload: Payload | null | undefined): Row[] {
  return (payload?.rows ?? []).map((r) => ({
    month: r.month,
    primary_category: r.primary_category ?? 'Uncategorised',
    sub_category: r.sub_category ?? 'Unknown',
    cost_type: r.cost_type ?? 'Unknown',
    nature: r.nature ?? 'Normal',
    household: cents(r.household),
    mine: cents(r.mine),
    household_to_day: cents(r.household_to_day),
    mine_to_day: cents(r.mine_to_day),
    count: Number(r.count ?? 0),
    source: r.source ?? '',
  }))
}

/**
 * Several payloads for the same window as one, each row tagged with its
 * `source` ("shared", "personal") so a view can keep some of them. Logging
 * began with the first expense of any of them.
 */
export function mergePayloads(bySource: Record<string, Payload | null | undefined>): Payload {
  const payloads = Object.entries(bySource).filter(([, p]) => p && typeof p === 'object') as [string, Payload][]
  const first = payloads[0]?.[1]
  const firsts = payloads.map(([, p]) => p.first_date).filter((d): d is string => !!d).sort()
  return {
    month: first?.month ?? '',
    months: first?.months ?? [],
    is_partial: first?.is_partial ?? false,
    as_of_day: first?.as_of_day ?? 0,
    rows: payloads.flatMap(([source, p]) => (p.rows ?? []).map((row) => ({ ...row, source }))),
    first_date: firsts[0] ?? null,
  }
}

// --- months logged in full ---------------------------------------------------

/** A month counts as logged in full when logging had begun by its 7th. */
export const TRACKED_BY_DAY = 7

/** The first month logged in full, from `first_date`: that month if logging began by the 7th, else the next. */
export function trackedSince(firstDate: string | null | undefined): string | null {
  if (!firstDate) return null
  const month = firstDate.slice(0, 7)
  return Number(firstDate.slice(8, 10)) <= TRACKED_BY_DAY ? month : shiftMonth(month, 1)
}

/** The day logging began in `month` when it began there after the 7th (a month logged in part), else null. */
export function partlyLoggedFrom(month: string, firstDate: string | null | undefined): number | null {
  if (!firstDate || firstDate.slice(0, 7) !== month || Number(firstDate.slice(8, 10)) <= TRACKED_BY_DAY) return null
  return Number(firstDate.slice(8, 10))
}

export { ordinal }

export function lensColumn(lens: Lens | string, toDay = false): Amount {
  const col = lens === 'My share' || lens === 'mine' ? 'mine' : 'household'
  return (toDay ? `${col}_to_day` : col) as Amount
}

export function keepSources(rows: Row[], sources: string[] | null): Row[] {
  return sources === null ? rows : rows.filter((r) => sources.includes(r.source))
}

/** Total per month over `months` (zero-filled, in window order), as [month, cents][]. */
export function monthlyTotals(rows: Row[], months: string[], lens: Lens | string, toDay = false): Map<string, number> {
  const col = lensColumn(lens, toDay)
  const out = new Map(months.map((m) => [m, 0]))
  for (const r of rows) if (out.has(r.month)) out.set(r.month, out.get(r.month)! + r[col])
  return out
}

export function monthlyCounts(rows: Row[], months: string[]): Map<string, number> {
  const out = new Map(months.map((m) => [m, 0]))
  for (const r of rows) if (out.has(r.month)) out.set(r.month, out.get(r.month)! + r.count)
  return out
}

export function expenseCount(rows: Row[], month: string): number {
  return rows.filter((r) => r.month === month).reduce((s, r) => s + r.count, 0)
}

// --- comparisons -------------------------------------------------------------

export interface Comparison {
  key: string
  current: number
  previous: number
  change: number
  pct: number | null
}

const pct = (change: number, previous: number): number | null => (previous > 0 ? change / previous : null)

type By = 'primary_category' | 'sub_category' | 'cost_type'

/**
 * The selected month against the previous one, per `by` value. The previous
 * month counts only the same days while the selected month is in progress.
 * Largest current first (then by name); rows zero in both months dropped.
 */
export function compare(rows: Row[], selected: string, isPartial: boolean, lens: Lens | string,
  by: By = 'primary_category', where: Partial<Record<By, string>> = {}): Comparison[] {
  const previous = shiftMonth(selected, -1)
  const now = lensColumn(lens)
  const then = lensColumn(lens, isPartial)
  const acc = new Map<string, { current: number; previous: number }>()
  for (const r of rows) {
    if (Object.entries(where).some(([k, v]) => r[k as By] !== v)) continue
    if (r.month !== selected && r.month !== previous) continue
    const entry = acc.get(r[by]) ?? { current: 0, previous: 0 }
    if (r.month === selected) entry.current += r[now]
    else entry.previous += r[then]
    acc.set(r[by], entry)
  }
  return [...acc.entries()]
    .filter(([, v]) => v.current !== 0 || v.previous !== 0)
    .map(([key, v]) => ({ key, ...v, change: v.current - v.previous, pct: pct(v.current - v.previous, v.previous) }))
    .sort((a, b) => b.current - a.current || a.key.localeCompare(b.key))
}

/** The selected month's total against the previous month (same days if partial). */
export function compareTotal(rows: Row[], selected: string, isPartial: boolean, lens: Lens | string) {
  const previous = shiftMonth(selected, -1)
  const now = lensColumn(lens)
  const then = lensColumn(lens, isPartial)
  let current = 0
  let before = 0
  for (const r of rows) {
    if (r.month === selected) current += r[now]
    else if (r.month === previous) before += r[then]
  }
  return { current, previous: before, change: current - before, pct: pct(current - before, before) }
}

/**
 * Average of the n complete months just before `selected` (empty months
 * count as zero), or null until n such months exist: all inside the window,
 * none before the first month with data, none before `since`.
 */
export function previousFullAverage(rows: Row[], months: string[], selected: string, lens: Lens | string,
  n = 3, toDay = false, since: string | null = null): number | null {
  const wanted = Array.from({ length: n }, (_, k) => shiftMonth(selected, -(k + 1)))
  if (!rows.length || wanted.some((m) => !months.includes(m))) return null
  const earliest = rows.reduce((min, r) => (r.month < min ? r.month : min), rows[0].month)
  const oldest = wanted[wanted.length - 1]
  if (oldest < earliest || (since !== null && oldest < since)) return null
  const totals = monthlyTotals(rows, months, lens, toDay)
  return Math.round(wanted.reduce((s, m) => s + (totals.get(m) ?? 0), 0) / n)
}

/** The key whose spending rose most in R$, or null if nothing rose. */
export function biggestIncrease(comparison: Comparison[]): string | null {
  const rising = comparison.filter((c) => c.change > 0)
  if (!rising.length) return null
  return [...rising].sort((a, b) => b.change - a.change || a.key.localeCompare(b.key))[0].key
}

/** Rows that changed, largest absolute change first. */
export function biggestChanges(comparison: Comparison[]): Comparison[] {
  return comparison.filter((c) => c.change !== 0)
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change) || a.key.localeCompare(b.key))
}

// --- text ----------------------------------------------------------------------

/** 0.125 → '+12,5%'; null → 'new'. */
export function changePct(p: number | null): string {
  if (p === null || Number.isNaN(p)) return 'new'
  const v = (p * 100).toFixed(1).replace('.', ',')
  return p >= 0 ? `+${v}%` : `${v}%`
}

/** '+R$ 12,50 (+5,0%)', or '+R$ 50,00 (new)' when there was nothing before. */
export function deltaText(change: number, p: number | null): string {
  return `${signedBrl(change)} (${changePct(p)})`
}

export type Line = [string, 'more' | 'less' | null]

/** '▲ R$ 120 (12%) vs Sep 26', toned: spending up is "more" (orange). One short line (lib/delta.ts). */
export function deltaLine(change: number, p: number | null, against: string): Line {
  if (p === null || Number.isNaN(p)) return delta(change, null, against)
  // delta() wants the earlier amount; recover it from the change and its share.
  return delta(change, p ? change / p : null, against)
}

// --- what we control, fixed costs, one-offs ----------------------------------------

export const ONE_OFFS = ['Annual', 'Extraordinary']
/** "Above usual": more than 10% over it. */
export const ABOVE = 1.1

/** Spending that depends on how we live: cost type Variable, one-offs left out. */
export const controllable = (rows: Row[]) => rows.filter((r) => r.cost_type === 'Variable' && !ONE_OFFS.includes(r.nature))
/** Fixed costs that recur (rent, internet, subscriptions), one-offs left out. */
export const fixedCosts = (rows: Row[]) => rows.filter((r) => r.cost_type === 'Fixed' && !ONE_OFFS.includes(r.nature))
/** Annual and extraordinary costs. */
export const oneOffs = (rows: Row[]) => rows.filter((r) => ONE_OFFS.includes(r.nature))

/**
 * The usual month before `month`: the average of up to n months before it
 * logged in full (from `since`), from a per-month series; null before any.
 */
export function usualBefore(totals: Map<string, number>, month: string, since: string | null, n = 3): number | null {
  const before = [...totals.keys()].filter((m) => m < month && (since === null || m >= since)).slice(-n)
  if (!before.length) return null
  return Math.round(before.reduce((s, m) => s + (totals.get(m) ?? 0), 0) / before.length)
}

export interface ControlRow {
  name: string
  current: number
  usual: number | null
  change: number | null
  pct: number | null
  /** The last `shown` months, [month, cents]. */
  series: [string, number][]
  /** Months in a row, up to this one, above their own usual. */
  streak: number
}

/**
 * "Are the costs we control changing?": per primary category of
 * controllable() spending, biggest this month first, against its usual month
 * (same days while the month is going), with the last `shown` months and the
 * streak of months above usual (two or more is a habit, not a blip).
 */
export function controlRows(rows: Row[], months: string[], selected: string, lens: Lens | string,
  isPartial: boolean, since: string | null, shown = 6): ControlRow[] {
  const d = controllable(rows)
  const window = months.slice(-shown)
  const names = [...new Set(d.map((r) => r.primary_category))]
  const out: ControlRow[] = []
  for (const name of names) {
    const mine = d.filter((r) => r.primary_category === name)
    const full = monthlyTotals(mine, months, lens)
    const toDay = monthlyTotals(mine, months, lens, true)
    const current = full.get(selected) ?? 0
    const series = window.map((m) => [m, full.get(m) ?? 0] as [string, number])
    if (!series.some(([, v]) => v)) continue
    const usual = usualBefore(isPartial ? toDay : full, selected, since)
    let streak = 0
    for (const m of months.filter((x) => x <= selected).reverse()) {
      const base = usualBefore(m === selected && isPartial ? toDay : full, m, since)
      if (base === null || (full.get(m) ?? 0) <= base * ABOVE) break
      streak += 1
    }
    const change = usual !== null ? current - usual : null
    out.push({ name, current, usual, change, pct: usual ? pct(change!, usual) : null, series, streak })
  }
  return out.sort((a, b) => b.current - a.current || a.name.localeCompare(b.name))
}

function names(list: string[]): string {
  return list.length === 1 ? list[0] : `${list.slice(0, -1).join(', ')} and ${list[list.length - 1]}`
}

/**
 * The control card's answer in sentences: what has been above usual for two
 * months or more, where the most could be saved, or that all is near usual.
 */
export function controlLines(rows: ControlRow[]): Line[] {
  const compared = rows.filter((r) => r.usual !== null)
  if (!compared.length) return [['The usual month appears once a whole month has been logged.', null]]
  const lines: Line[] = []
  const habit = compared.filter((r) => r.streak >= 2).map((r) => r.name)
  if (habit.length) lines.push([`Above usual for two months or more: ${names(habit)}.`, 'more'])
  const over = compared.filter((r) => r.usual && r.current > r.usual * ABOVE)
    .sort((a, b) => (b.change ?? 0) - (a.change ?? 0)).slice(0, 3)
  if (over.length) {
    lines.push([`Where you could save: ${over.map((r) => `${r.name} ${formatBrl(r.change ?? 0)} above usual`).join('; ')}.`, null])
  }
  if (!lines.length) lines.push(['Everything you control is within 10% of usual.', 'less'])
  return lines
}

/** The suggested monthly reserve is rounded up to R$ 50 (in cents). */
export const RESERVE_ROUND = 5000
/** Months logged in full before the reserve is more than a rough guess. */
export const RESERVE_SOLID = 6

export interface Reserve {
  monthly: number
  months: number
  rough: boolean
  /** [sub-category, the month it's next due, what it cost last time]. */
  coming: [string, string, number][]
}

/**
 * How much to set aside a month for one-offs: what annual and extraordinary
 * costs averaged per month over the months logged in full before `selected`
 * (rounded up to R$ 50; rough while fewer than six), and the annual bills of
 * the last year coming round again, soonest first. Null before a whole month.
 */
export function reserve(rows: Row[], months: string[], selected: string, lens: Lens | string,
  since: string | null): Reserve | null {
  const full = months.filter((m) => m < selected && (since === null || m >= since))
  if (!full.length) return null
  const offs = oneOffs(rows)
  const col = lensColumn(lens)
  const total = offs.filter((r) => full.includes(r.month)).reduce((s, r) => s + r[col], 0)
  const monthly = Math.ceil(total / full.length / RESERVE_ROUND - 1e-9) * RESERVE_ROUND
  const bySubMonth = new Map<string, number>()
  for (const r of offs) {
    if (r.nature !== 'Annual' || !months.includes(r.month)) continue
    const k = `${r.sub_category}\u0000${r.month}`
    bySubMonth.set(k, (bySubMonth.get(k) ?? 0) + r[col])
  }
  const latest = new Map<string, [string, number]>()
  for (const [k, v] of bySubMonth) {
    const [sub, month] = k.split('\u0000')
    const seen = latest.get(sub)
    if (!seen || month > seen[0]) latest.set(sub, [month, v])
  }
  const coming = [...latest.entries()].filter(([, [, v]]) => v > 0)
    .map(([sub, [month, v]]) => [sub, shiftMonth(month, 12), v] as [string, string, number])
    .sort((a, b) => a[1].localeCompare(b[1]) || a[0].localeCompare(b[0]))
  return { monthly, months: full.length, rough: full.length < RESERVE_SOLID, coming }
}

/** The reserve as the One-offs card says it. */
export function reserveLines(r: Reserve | null): Line[] {
  if (!r) return [['A reserve to set aside appears once a whole month has been logged.', null]]
  const span = `${r.months} month${r.months !== 1 ? 's' : ''}`
  const lines: Line[] = [[`Set aside about ${formatBrl(r.monthly)} a month for them` +
    (r.rough ? ` (a rough guess from ${span} logged)` : ` (from the last ${span})`), null]]
  for (const [name, month, amount] of r.coming.slice(0, 3)) {
    lines.push([`Coming round: ${name} in ${monthLabel(month, true)}, ${formatBrl(amount)} last time`, null])
  }
  return lines
}
