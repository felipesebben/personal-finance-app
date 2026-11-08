/**
 * The login briefing on Home: a few sentences on how this month is going,
 * built from numbers the API already computes. Every line is optional: one
 * with nothing to say is left out. Port of frontend/briefing.py (with the
 * few analytics_shaping helpers it needs); tests in briefing.test.ts.
 */
import { addMonths, monthName, ordinal } from './dates'
import { cents, formatBrl } from './money'
import { runOutText, type JointStatus } from './joint'

export interface AnalyticsRow {
  month: string
  primary_category: string
  sub_category?: string | null
  cost_type?: string | null
  nature?: string | null
  household: string | number
  mine: string | number
  count?: number
  household_to_day: string | number
  mine_to_day: string | number
}

export interface AnalyticsPayload {
  month: string
  months: string[]
  is_partial: boolean
  as_of_day: number
  rows: AnalyticsRow[]
  first_date?: string | null
}

export type Lens = 'household' | 'mine'

function sum(rows: AnalyticsRow[], month: string, lens: Lens, toDay: boolean): number {
  const col = (toDay ? `${lens}_to_day` : lens) as keyof AnalyticsRow
  return rows.filter((r) => r.month === month).reduce((s, r) => s + cents(r[col] as string), 0)
}

/** The average of the three months before `month`, or null until all three are in the window and in the data. */
function previousFullAverage(p: AnalyticsPayload, lens: Lens, toDay: boolean): number | null {
  const wanted = [1, 2, 3].map((k) => addMonths(p.month, -k))
  if (!p.rows.length || wanted.some((m) => !p.months.includes(m))) return null
  const first = p.rows.map((r) => r.month).sort()[0]
  if (wanted.some((m) => m < first)) return null
  return Math.round(wanted.reduce((s, m) => s + sum(p.rows, m, lens, toDay), 0) / wanted.length)
}

function versus(change: number, against: string): string {
  if (change === 0) return `the same as ${against}`
  return change > 0
    ? `▲ ${formatBrl(change)} more than ${against}`
    : `▼ ${formatBrl(-change)} less than ${against}`
}

/**
 * "Shared: R$ 1.840,00 so far in October, ▲ R$ 210,00 more than usual by
 * the 16th. Biggest: Food." "Usual" is the average of the three previous
 * full months over the same days; without them it falls back to last month,
 * and without that it makes no comparison. Null when there's nothing at all.
 */
export function spendingLine(label: string, p: AnalyticsPayload | null | undefined, lens: Lens,
  topCategory = false): string | null {
  if (!p || !p.rows?.length) return null
  const { month, is_partial: partial, as_of_day: day } = p
  const current = sum(p.rows, month, lens, false)
  const previousMonth = addMonths(month, -1)
  const previous = sum(p.rows, previousMonth, lens, partial)
  let text = `${label}: ${formatBrl(current)} ${partial ? 'so far in' : 'in'} ${monthName(month)}`
  const byNow = partial ? ` by the ${ordinal(day)}` : ''
  const average = previousFullAverage(p, lens, partial)
  if (average !== null) {
    text += `, ${versus(current - average, `usual${byNow}`)}`
  } else if (previous || p.rows.some((r) => r.month === previousMonth)) {
    text += `, ${versus(current - previous, `${monthName(previousMonth)}${byNow}`)}`
  }
  text += '.'
  if (topCategory) {
    const totals = new Map<string, number>()
    for (const r of p.rows.filter((r) => r.month === month)) {
      totals.set(r.primary_category, (totals.get(r.primary_category) ?? 0) + cents(r[lens]))
    }
    if (totals.size) {
      const biggest = [...totals].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0]
      text += ` Biggest: ${biggest}.`
    }
  }
  return text
}

/** Shared and personal payloads for the same window as one (my share of shared + my personal). */
export function mergeForMine(...payloads: (AnalyticsPayload | null | undefined)[]): AnalyticsPayload | null {
  const present = payloads.filter((p): p is AnalyticsPayload => !!p)
  if (!present.length) return null
  return { ...present[0], rows: present.flatMap((p) => p.rows ?? []) }
}

export interface Transfer {
  from_user_id: number
  from_name: string | null
  to_user_id: number
  to_name: string | null
  amount: string
}

/** Who owes whom this month, from my point of view; null without a balance report. */
export function settleLine(balances: { transfers?: Transfer[] } | null | undefined, me: number | null,
  month: string): string | null {
  if (!balances || !Array.isArray(balances.transfers)) return null
  if (!balances.transfers.length) return `Settle up: all square for ${month}.`
  const parts = balances.transfers.map((t) => {
    const amount = formatBrl(cents(t.amount))
    if (t.to_user_id === me) return `${t.from_name} owes you ${amount}`
    if (t.from_user_id === me) return `you owe ${t.to_name} ${amount}`
    return `${t.from_name} owes ${t.to_name} ${amount}`
  })
  const text = parts.join('; ')
  return `Settle up: ${text[0].toUpperCase()}${text.slice(1)} for ${month}.`
}

/** One line per joint account with a known balance, named only when there are several. */
export function jointLines(statuses: Pick<JointStatus, 'label' | 'balance' | 'runs_out_on' | 'month'>[] | null | undefined): string[] {
  const known = (statuses ?? []).filter((s) => s.balance !== null && s.balance !== undefined)
  return known.map((s) => {
    const name = 'Joint account' + (known.length > 1 ? ` (${s.label})` : '')
    const left = `${name}: ${formatBrl(cents(s.balance))} left.`
    const pace = runOutText(s)
    return pace ? `${left} ${pace}` : left
  })
}
