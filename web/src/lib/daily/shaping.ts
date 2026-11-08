/**
 * Shaping /analytics/{shared,personal}/daily for the "This month" view: how
 * this month is going day by day against earlier months, and where the
 * money goes. Port of the Streamlit frontend's daily_shaping.py; pure, so
 * it's unit-tested in shaping.test.ts. Amounts are cents.
 *
 * The API sends one row per day × category × cost type × nature, so the
 * page can narrow what it counts (lib/filtering.ts) before anything is
 * added up: `readRows` reads them, filterRows narrows them, `byDay` sums
 * them per day.
 *
 * Comparisons only use months logged in full (`trackedSince`): a month
 * whose logging began after its 7th is shown for context, never for a ▲/▼.
 */
import { addMonths, daysInMonth, monthLabel, monthName, ordinal, weekday } from '../dates'
import { cents, formatBrl, shortBrl } from '../money'
import { delta } from '../delta'

export type Lens = 'Household' | 'My share'

export interface ApiDailyRow {
  date: string
  primary_category: string
  sub_category: string
  cost_type: string
  nature: string
  household: string | number
  mine: string | number
  count: number
  source?: string
}

export interface DailyPayload {
  month: string
  months: string[]
  is_partial: boolean
  as_of_day: number
  today?: string
  rows: ApiDailyRow[]
}

export interface Row {
  date: string
  month: string
  day: number
  primary_category: string
  sub_category: string
  cost_type: string
  nature: string
  household: number
  mine: number
  count: number
  source: string
}

export interface Day {
  date: string
  month: string
  day: number
  household: number
  mine: number
  count: number
  top_category: string
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
/** A month counts as logged in full when logging had begun by its 7th. */
export const TRACKED_BY_DAY = 7

/** One vocabulary across the app, each comparison named by the question it answers. */
export const BASELINES = {
  last: ['Last month', 'what changed?'],
  usual: ['Usual month', 'is this normal?'],
  year: ['12-month average', 'where is the trend going?'],
  last_year: ['Same month last year', 'is it the season?'],
  target: ['Target', 'are we on plan?'],
} as const
export type Baseline = keyof typeof BASELINES

export const col = (lens: Lens) => (lens === 'Household' ? 'household' : 'mine') as 'household' | 'mine'
const pct0 = (x: number) => `${Math.round(Math.abs(x) * 100)}%`
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0)

// --- rows, merging and days -------------------------------------------------

/** Several daily payloads for the same window as one, each row tagged with its source. */
export function mergePayloads(bySource: Record<string, DailyPayload | null | undefined>): DailyPayload | null {
  const entries = Object.entries(bySource).filter(([, p]) => p && typeof p === 'object') as [string, DailyPayload][]
  if (!entries.length) return null
  return { ...entries[0][1], rows: entries.flatMap(([source, p]) => (p.rows ?? []).map((r) => ({ ...r, source }))) }
}

export function readRows(payload: DailyPayload | null | undefined): Row[] {
  return (payload?.rows ?? []).map((r) => ({
    date: r.date.slice(0, 10),
    month: r.date.slice(0, 7),
    day: Number(r.date.slice(8, 10)),
    primary_category: r.primary_category,
    sub_category: r.sub_category,
    cost_type: r.cost_type,
    nature: r.nature,
    household: cents(r.household),
    mine: cents(r.mine),
    count: Number(r.count) || 0,
    source: r.source ?? '',
  }))
}

/** One entry per day with spending, oldest first, with its top category (a tie goes to the first name). */
export function byDay(rows: Row[]): Day[] {
  const days = new Map<string, Day & { cats: Map<string, number> }>()
  for (const r of rows) {
    let d = days.get(r.date)
    if (!d) {
      d = { date: r.date, month: r.month, day: r.day, household: 0, mine: 0, count: 0, top_category: '', cats: new Map() }
      days.set(r.date, d)
    }
    d.household += r.household
    d.mine += r.mine
    d.count += r.count
    d.cats.set(r.primary_category, (d.cats.get(r.primary_category) ?? 0) + r.household)
  }
  return [...days.values()].sort((a, b) => a.date.localeCompare(b.date)).map(({ cats, ...d }) => {
    const top = [...cats].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]
    return { ...d, top_category: top?.[0] ?? '' }
  })
}

/** The first month logged in full, from the rows before any filter. */
export function trackedSince(rows: Row[]): string | null {
  const first = loggingStarted(rows)
  if (!first) return null
  return Number(first.slice(8, 10)) <= TRACKED_BY_DAY ? first.slice(0, 7) : addMonths(first.slice(0, 7), 1)
}

/** The first day with spending, "YYYY-MM-DD". */
export function loggingStarted(rows: Row[]): string | null {
  return rows.length ? rows.reduce((m, r) => (r.date < m ? r.date : m), rows[0].date) : null
}

/** The day logging started in `month` when it was logged only in part, else null. */
export function partlyLoggedFrom(month: string, since: string | null, started: string | null): number | null {
  if (!started || started.slice(0, 7) !== month || (since !== null && since <= month)) return null
  return Number(started.slice(8, 10))
}

const sinceOr = (days: Day[], since: string | null | undefined) =>
  since ?? (days.length ? days.reduce((m, d) => (d.month < m ? d.month : m), days[0].month) : null)

/** Spending on each day 1..n of `month` (index 0 = the 1st), zero where nothing was spent. */
export function dailyAmounts(days: Day[], month: string, lens: Lens): number[] {
  const out = new Array(daysInMonth(month)).fill(0)
  const c = col(lens)
  for (const d of days) if (d.month === month) out[d.day - 1] += d[c]
  return out
}

export function cumulative(values: number[]): number[] {
  let t = 0
  return values.map((v) => (t += v))
}

/** Spent in `month` from the 1st to `day` (its last day, if shorter). */
function cumulativeTo(days: Day[], month: string, lens: Lens, day: number): number {
  return sum(dailyAmounts(days, month, lens).slice(0, day))
}

// --- the comparisons ----------------------------------------------------------

const BASELINE_STEPS: Record<string, number[]> = {
  last: [1], usual: [1, 2, 3], year: Array.from({ length: 12 }, (_, i) => i + 1), last_year: [12],
}

/**
 * The months a comparison averages over ("last": the month before; "usual":
 * the three before; "year": the twelve before; "last_year": the same month a
 * year earlier), or [] when the window or the tracking doesn't reach back
 * that far. `month` defaults to the payload's.
 */
export function baselineMonths(days: Day[], data: DailyPayload, key: string, since?: string | null,
  month: string = data.month): string[] {
  const from = sinceOr(days, since)
  const steps = BASELINE_STEPS[key]
  if (!steps) return []
  const months = steps.map((k) => addMonths(month, -k))
  if (from === null || months.some((m) => !data.months.includes(m)) || months.some((m) => m < from)) return []
  return months
}

/** The average running total of `months`, by day 1..n of the selected month (a shorter month carries on). */
export function averageCumulative(days: Day[], data: DailyPayload, lens: Lens, months: string[]): number[] {
  const n = daysInMonth(data.month)
  const curves = months.map((m) => {
    const c = cumulative(dailyAmounts(days, m, lens))
    return Array.from({ length: n }, (_, i) => c[Math.min(i, c.length - 1)] ?? 0)
  })
  return Array.from({ length: n }, (_, i) => sum(curves.map((c) => c[i])) / curves.length)
}

export interface Pace {
  month: string
  previous: string
  day: number
  days: number
  is_partial: boolean
  since: string | null
  so_far: number
  last_by_day: number
  last_total: number
  last_usual: number | null
  has_last: boolean
  last_partly_from: number | null
  usual_by_day: number | null
  usual_total: number | null
  usual_of: string[]
  heading_for: number | null
  per_day: number
  last_per_day: number
  usual_per_day: number | null
  days_with_spending: number
  days_left: number
  reference: number | null
  reference_name: string | null
  allowance: number | null
}

/**
 * The numbers behind the headline and the cards: spent so far, the same days
 * of last month and of the usual month, whole-month figures, and what's left
 * to spend per day to stay within the usual month (or last month).
 */
export function pace(days: Day[], data: DailyPayload, lens: Lens, since?: string | null,
  started: string | null = null): Pace {
  const { month, as_of_day: day } = data
  const from = sinceOr(days, since)
  const previous = addMonths(month, -1)
  const n = daysInMonth(month)
  const thisMonth = dailyAmounts(days, month, lens)
  const last = dailyAmounts(days, previous, lens)
  const usualOf = baselineMonths(days, data, 'usual', from)
  const usual = usualOf.length ? averageCumulative(days, data, lens, usualOf) : null
  const soFar = sum(thisMonth.slice(0, day))
  const hasLast = from !== null && from <= previous
  const lastTotal = sum(last)
  const usualTotal = usual ? Math.round(usual[n - 1]) : null
  const usualByDay = usual ? Math.round(usual[day - 1]) : null
  const lastUsualOf = baselineMonths(days, data, 'usual', from, previous)
  const lastUsual = lastUsualOf.length
    ? Math.round(sum(lastUsualOf.map((m) => sum(dailyAmounts(days, m, lens)))) / 3) : null
  let reference: number | null = null
  let referenceName: string | null = null
  if (usualTotal !== null) [reference, referenceName] = [usualTotal, 'usual']
  else if (hasLast) [reference, referenceName] = [lastTotal, monthName(previous)]
  const daysLeft = data.is_partial ? n - day : 0
  const lastDays = Math.min(day, last.length)
  const lastByDay = sum(last.slice(0, lastDays))
  return {
    month, previous, day, days: n, is_partial: data.is_partial, since: from,
    so_far: soFar,
    last_by_day: lastByDay,
    last_total: lastTotal,
    last_usual: lastUsual,
    has_last: hasLast,
    last_partly_from: partlyLoggedFrom(previous, from, started),
    usual_by_day: usualByDay,
    usual_total: usualTotal,
    usual_of: [...usualOf].sort(),
    heading_for: usualTotal !== null && usualByDay !== null && data.is_partial ? soFar + usualTotal - usualByDay : null,
    per_day: day ? Math.round(soFar / day) : 0,
    last_per_day: Math.round(lastByDay / lastDays),
    usual_per_day: usualByDay === null ? null : Math.round(usualByDay / day),
    days_with_spending: thisMonth.slice(0, day).filter((v) => v > 0).length,
    days_left: daysLeft,
    reference,
    reference_name: referenceName,
    allowance: reference !== null && daysLeft && soFar < reference ? Math.round((reference - soFar) / daysLeft) : null,
  }
}

export type Line = [string, 'more' | 'less' | null]

/** ['▲ R$ 150 (12%) vs September', 'more']: one short line, the tone colours it (lib/delta.ts). */
export function versus(change: number, previous: number, against: string): Line {
  return delta(change, previous, against)
}

export interface Headline { label: string; amount: string; lines: Line[] }

/**
 * The hero, leading with the answer: "Spent so far in October", the amount,
 * and short lines like "▲ R$ 210 (13%) vs September" (same days while the
 * month is going; the card's (i) says so).
 * `focus` (filtering.note) is added to the label when something is filtered
 * out; `started` explains a missing comparison.
 */
export function headline(p: Pace, focus = '', started: string | null = null): Headline {
  const name = monthName(p.month)
  const previous = monthName(p.previous)
  let label = p.is_partial ? `Spent so far in ${name}` : `Spent in ${name}`
  if (focus) label += ` · ${focus}`
  const lines: Line[] = []
  if (p.has_last) lines.push(versus(p.so_far - p.last_by_day, p.last_by_day, previous))
  if (p.usual_by_day !== null) lines.push(versus(p.so_far - p.usual_by_day, p.usual_by_day, 'usual'))
  if (p.heading_for !== null) lines.push([`Heading for about ${shortBrl(p.heading_for)}`, null])
  if (!lines.length && p.last_partly_from) {
    lines.push([`${previous}: ${shortBrl(p.last_total)}, logged from the ${ordinal(p.last_partly_from)}`, null])
  }
  if (!p.has_last && p.usual_by_day === null) {
    const start = started
      ? `Logging started on ${Number(started.slice(8, 10))} ${monthName(started.slice(0, 7))}, so c` : 'C'
    const first = p.since
      ? `in ${monthName(addMonths(p.since, 1))}, against ${monthName(p.since)}` : 'once a whole month has been logged'
    lines.push([lines.length ? `Comparisons start ${first}.` : `Nothing to compare with yet. ${start}omparisons start ${first}.`,
      null])
  }
  return { label, amount: formatBrl(p.so_far), lines }
}

// --- the KPI cards --------------------------------------------------------------

export interface KpiCard {
  key: 'last' | 'usual' | 'allowance' | 'days'
  label: string
  value: string
  lines: Line[]
  help: string
}

/**
 * The cards under the hero: last month, the usual month and what's left
 * per day (or, for a finished month, days with spending). The Streamlit
 * view's "Per day so far" card was dropped: its ▲/▼ against usual is the
 * hero's own line divided by the same number of days.
 */
export function cards(p: Pace): KpiCard[] {
  const previous = monthName(p.previous)
  const by = `by the ${ordinal(p.day)}`
  const out: KpiCard[] = []

  let lines: Line[] = []
  if (p.has_last) {
    if (p.is_partial) lines.push([`${shortBrl(p.last_by_day)} ${by}`, null])
    if (p.last_usual !== null) lines.push(versus(p.last_total - p.last_usual, p.last_usual, 'its usual'))
  }
  const partly = p.last_partly_from
  if (!p.has_last && partly) lines = [[`Logged only from the ${ordinal(partly)}, so not compared.`, null]]
  out.push({
    key: 'last', label: `Last month · ${previous}`,
    value: p.has_last || partly ? formatBrl(p.last_total) : '—',
    lines: lines.length ? lines : [['Not logged in full, so not compared.', null]],
    help: `All of ${previous}, finished${p.is_partial ? `; ${formatBrl(p.last_by_day)} of it ${by}` : ''}. "Its usual" is the average of the three months before it. The bars are each month's total.`,
  })

  if (p.usual_total !== null) {
    const span = `${monthName(p.usual_of[0])}–${monthName(p.usual_of[p.usual_of.length - 1])}`
    lines = [[`Average of ${span}`, null]]
    if (p.is_partial && p.usual_by_day !== null) lines.push([`${shortBrl(p.usual_by_day)} ${by}`, null])
    out.push({ key: 'usual', label: 'Usual month', value: formatBrl(p.usual_total), lines,
      help: `The average of ${span}, the three months before this one: what a normal month costs. The bars are those three months, the line their average.` })
  } else {
    out.push({ key: 'usual', label: 'Usual month', value: '—', lines: [['Needs three months of history.', null]],
      help: 'The average of the three months before this one: what a normal month costs.' })
  }

  if (p.is_partial && p.reference !== null && p.days_left) {
    const ref = p.reference_name === 'usual' ? 'the usual month' : p.reference_name!
    // How much is spent against how much of the month has gone is the bar under the card, not another line.
    const spentShare = p.reference ? p.so_far / p.reference : 0
    const pace = `${pct0(spentShare)} of ${ref} spent with ${pct0(p.day / p.days)} of the month gone.`
    const left = `${p.days_left} day${p.days_left === 1 ? '' : 's'} left`
    if (p.allowance !== null) {
      out.push({ key: 'allowance', label: `To stay within ${ref}`, value: `${formatBrl(p.allowance)} a day`,
        lines: [[left, null]],
        help: `What's left of ${ref} (${formatBrl(p.reference)}) divided by the days after today. ${pace} The bar is how much of it is spent; the tick, how much of the month has gone.` })
    } else {
      out.push({ key: 'allowance', label: `Past ${ref}`, value: formatBrl(p.so_far - p.reference),
        lines: [[`▲ over ${ref} · ${left}`, 'more']],
        help: `Spent so far beyond ${ref} (${formatBrl(p.reference)}). ${pace}` })
    }
  } else {
    out.push({ key: 'days', label: 'Days with spending', value: `${p.days_with_spending} of ${p.day}`,
      lines: [['Days with at least one expense', null]], help: "The bars are each day's spending." })
  }
  return out
}

export interface MonthHistory {
  month: string
  label: string
  total: number
  to_day: number
  per_day: number
  is_selected: boolean
}

/** Every tracked month of the window, oldest first: its total, what it had spent by the selected day, per day. */
export function history(days: Day[], data: DailyPayload, lens: Lens, since?: string | null): MonthHistory[] {
  const { month, as_of_day: day } = data
  const from = sinceOr(days, since)
  return data.months.filter((m) => from !== null && m >= from).map((m) => {
    const amounts = dailyAmounts(days, m, lens)
    const toDay = cumulativeTo(days, m, lens, day)
    return {
      month: m, label: monthLabel(m, true).slice(0, 3),
      total: m === month ? sum(amounts.slice(0, day)) : sum(amounts),
      to_day: toDay, per_day: Math.round(toDay / Math.min(day, amounts.length)), is_selected: m === month,
    }
  })
}

// --- the running total ------------------------------------------------------------

export type Role = 'this' | 'last' | 'usual' | 'year' | 'last_year' | 'target'

export interface TrackSeries {
  name: string
  role: Role
  /** The running total by day, index 0 = the 1st. */
  values: number[]
}

/** The monthly target for what's counted: every category's, or only those left when the filters narrow it. */
export function targetTotal(targets: Map<string, number>, rows: Row[], narrowed: boolean): number {
  if (!targets.size) return 0
  const kept = narrowed && rows.length ? new Set(rows.map((r) => r.primary_category)) : null
  return sum([...targets].filter(([c]) => !kept || kept.has(c)).map(([, v]) => v))
}

/**
 * "Are we on track this month?": this month's running total by day, and every
 * comparison that has the data: last month (also a partly logged one, named
 * "September (from the 26th)", for context), the usual month, the 12-month
 * average, the same month last year, and the target as a steady pace.
 */
export function trackSeries(days: Day[], data: DailyPayload, lens: Lens, since?: string | null,
  started: string | null = null, target = 0): TrackSeries[] {
  const { month, as_of_day: day } = data
  const previous = addMonths(month, -1)
  const n = daysInMonth(month)
  const from = sinceOr(days, since)
  const partly = partlyLoggedFrom(previous, from, started)
  const out: TrackSeries[] = [{
    name: `${monthName(month)}${data.is_partial ? ' so far' : ''}`, role: 'this',
    values: cumulative(dailyAmounts(days, month, lens)).slice(0, day),
  }]
  if (baselineMonths(days, data, 'last', from).length || partly) {
    out.push({ name: monthName(previous) + (partly ? ` (from the ${ordinal(partly)})` : ''), role: 'last',
      values: cumulative(dailyAmounts(days, previous, lens)) })
  }
  for (const key of ['usual', 'year', 'last_year'] as const) {
    const months = baselineMonths(days, data, key, from)
    if (months.length) out.push({ name: BASELINES[key][0], role: key, values: averageCumulative(days, data, lens, months) })
  }
  if (target > 0) {
    out.push({ name: BASELINES.target[0], role: 'target', values: Array.from({ length: n }, (_, i) => (target * (i + 1)) / n) })
  }
  return out
}

export interface MonthTotal { month: string; label: string; amount: number; is_selected: boolean; is_partial: boolean }

/** Each month's total from the first one logged in full to the selected one. */
export function monthsFrame(days: Day[], data: DailyPayload, lens: Lens, since?: string | null): MonthTotal[] {
  const from = sinceOr(days, since)
  return data.months.filter((m) => from !== null && m >= from).map((m) => ({
    month: m, label: monthLabel(m, true), amount: sum(dailyAmounts(days, m, lens)),
    is_selected: m === data.month, is_partial: m === data.month && data.is_partial,
  }))
}

/** The months' reference lines: the 12-month average and the target, when there's one. */
export function monthReferences(days: Day[], data: DailyPayload, lens: Lens, since?: string | null,
  target = 0): [string, number][] {
  const refs: [string, number][] = []
  const months = baselineMonths(days, data, 'year', since)
  if (months.length) refs.push([BASELINES.year[0], Math.round(sum(months.map((m) => sum(dailyAmounts(days, m, lens)))) / 12)])
  if (target > 0) refs.push([BASELINES.target[0], target])
  return refs
}

// --- the calendar -------------------------------------------------------------------

export interface CalDay {
  date: string
  day: number
  week: number
  /** 0 = Monday. */
  weekday: number
  amount: number
  count: number
  top_category: string
  state: 'past' | 'today' | 'future'
  label: string
}

/** One entry per day of `month`, laid out as a calendar (weeks down, Monday first); future days carry no amount. */
export function calendarDays(days: Day[], month: string, lens: Lens, today: string): CalDay[] {
  const amounts = dailyAmounts(days, month, lens)
  const byDate = new Map(days.filter((d) => d.month === month).map((d) => [d.date, d]))
  const offset = weekday(`${month}-01`) - 1
  return amounts.map((amount, i) => {
    const d = i + 1
    const date = `${month}-${String(d).padStart(2, '0')}`
    const state = date > today ? 'future' : date === today ? 'today' : 'past'
    const wd = weekday(date) - 1
    const info = state === 'future' ? undefined : byDate.get(date)
    return {
      date, day: d, week: Math.floor((offset + d - 1) / 7), weekday: wd,
      amount: state === 'future' ? 0 : amount, count: info?.count ?? 0, top_category: info?.top_category ?? '',
      state, label: `${WEEKDAY_NAMES[wd]} ${d} ${monthName(month)}`,
    }
  })
}

/** pandas' default (linear) quantile. */
export function quantile(values: number[], q: number): number {
  const v = [...values].sort((a, b) => a - b)
  if (!v.length) return NaN
  const pos = (v.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return v[lo] + (v[hi] - v[lo]) * (pos - lo)
}

/**
 * Where the calendar's darkest green starts: a typical big day (the 90th
 * percentile of days with spending), so one large payment doesn't wash every
 * other day out to the palest shade.
 */
export function calendarScaleMax(amounts: number[], q = 0.9): number {
  const spent = amounts.filter((a) => a > 0)
  return spent.length ? Math.round(quantile(spent, q)) : 100
}

// --- where the money goes ------------------------------------------------------------

export interface Ranked { key: string; name: string; amount: number; share: number; text: string }

/** What a bar says at its tip: "R$ 4,1 mil · 59%". */
export const tipText = (amount: number, share: number) => `${shortBrl(amount)} · ${pct0(share)}`

/**
 * What was spent per `by` (primary_category, sub_category, or "item" =
 * "Primary › sub") in `month` or on `date`, biggest first (a tie goes to the
 * name). Empty when nothing was spent.
 */
export function ranked(rows: Row[], lens: Lens, by: 'primary_category' | 'sub_category' | 'item',
  where: { month?: string; date?: string } = {}): Ranked[] {
  const c = col(lens)
  const totals = new Map<string, number>()
  for (const r of rows) {
    if (where.month !== undefined && r.month !== where.month) continue
    if (where.date !== undefined && r.date !== where.date) continue
    const name = by === 'item' ? `${r.primary_category} › ${r.sub_category}` : r[by]
    totals.set(name, (totals.get(name) ?? 0) + r[c])
  }
  const kept = [...totals].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const total = sum(kept.map(([, v]) => v))
  return kept.map(([name, amount]) => ({ key: name, name, amount, share: amount / total, text: tipText(amount, amount / total) }))
}

/**
 * What each name cost last month by the same `day`, for a grey tick on its
 * bar; with it, the tip says the change: "R$ 1,2 mil · ▲ 33%" ("· new" when
 * there was nothing before, "· same" when unchanged).
 */
export function againstLastMonth(items: Ranked[], rows: Row[], lens: Lens, by: 'primary_category' | 'sub_category',
  month: string, day: number): (Ranked & { previous: number })[] {
  const previous = addMonths(month, -1)
  const cut = Math.min(day, daysInMonth(previous))
  const c = col(lens)
  const sums = new Map<string, number>()
  for (const r of rows) if (r.month === previous && r.day <= cut) sums.set(r[by], (sums.get(r[by]) ?? 0) + r[c])
  return items.map((it) => {
    const then = sums.get(it.name) ?? 0
    return { ...it, previous: then, text: `${shortBrl(it.amount)} · ${moveText(it.amount, then)}` }
  })
}

/** "▲ 33%", "▼ 47%", "same", or "new" when there was nothing before. */
export function moveText(now: number, then: number): string {
  if (then <= 0) return 'new'
  const change = (now - then) / then
  return Math.abs(change) < 0.005 ? 'same' : `${change > 0 ? '▲' : '▼'} ${pct0(change)}`
}

export interface BigDay extends Ranked { top_category: string; count: number }

/** The month's n biggest days, biggest first (a tie goes to the earlier day): "Fri 10 Oct", "R$ 812 · Food". */
export function biggestDays(days: Day[], month: string, lens: Lens, n = 8): BigDay[] {
  const c = col(lens)
  const inMonth = days.filter((d) => d.month === month && d[c] > 0)
  const total = sum(inMonth.map((d) => d[c]))
  return [...inMonth].sort((a, b) => b[c] - a[c] || a.date.localeCompare(b.date)).slice(0, n).map((d) => ({
    key: d.date,
    name: `${WEEKDAYS[weekday(d.date) - 1]} ${d.day} ${monthName(d.month).slice(0, 3)}`,
    amount: d[c], share: d[c] / total, text: `${shortBrl(d[c])} · ${d.top_category}`,
    top_category: d.top_category, count: d.count,
  }))
}

export interface DayExpense {
  transaction_timestamp: string
  primary_category: string
  sub_category: string
  price: string | number
  mine: string | number
  payment_method?: string | null
  institution?: string | null
  paid_by?: string | null
}

export interface DayItem extends Ranked { detail: string }

/** "14:30" in São Paulo for an API timestamp. */
export function spTime(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit', hour12: false })
    .format(d)
}

/**
 * A day's expenses (already filtered) as bars, biggest first: "Groceries ·
 * 14:30" (unique; a sub-category named like a category keeps its category,
 * "Pets › Food"), its share of the day, and who paid and how for the tooltip.
 */
export function dayItems(items: DayExpense[], lens: Lens): DayItem[] {
  const clash = new Set(items.map((i) => i.primary_category))
  const rows = items.map((i) => ({ i, amount: cents(lens === 'Household' ? i.price : i.mine) })).filter((x) => x.amount > 0)
    .map(({ i, amount }) => {
      const what = clash.has(i.sub_category) && i.sub_category !== i.primary_category
        ? `${i.primary_category} › ${i.sub_category}` : i.sub_category
      const paid = i.institution ? `${i.payment_method} · ${i.institution}` : (i.payment_method ?? '')
      return { name: `${what} · ${spTime(i.transaction_timestamp)}`, amount, detail: i.paid_by ? `${paid}, paid by ${i.paid_by}` : paid }
    })
    .sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name))
  const seen = new Map<string, number>()
  const total = sum(rows.map((r) => r.amount))
  return rows.map((r) => {
    const k = (seen.get(r.name) ?? 0) + 1
    seen.set(r.name, k)
    const name = k > 1 ? `${r.name} (${k})` : r.name
    return { key: name, name, amount: r.amount, share: r.amount / total, text: tipText(r.amount, r.amount / total), detail: r.detail }
  })
}
