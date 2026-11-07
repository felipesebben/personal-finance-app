/**
 * The Joint account tab: turn one /joint/status item into chart series and
 * the sentences around it. Port of frontend/joint_shaping.py; tests in
 * joint.test.ts.
 */
import { cents, formatBrl, signedBrl } from './money'
import { monthName, ordinal, TZ } from './dates'
import type { HouseholdMember } from './household'

export const THIS_MONTH = 'This month'
export const USUAL = 'Usual (last 3 full months)'

export interface JointDay {
  day: number
  this_month: string | null
  usual: string | null
}

export interface JointStatus {
  payment_method_id: number
  label: string
  balance: string | null
  counted_from: string | null
  deposits_since: string
  spent_since: string
  month: string
  as_of_day: number
  days_in_month: number
  spent_to_day: string
  usual_to_day: string | null
  usual_month_total: string | null
  history_months: number
  runs_out_on: string | null
  days: JointDay[]
}

export interface JointEntry {
  joint_entry_id: number
  payment_method_id: number
  kind: 'deposit' | 'balance' | string
  amount: string
  entry_at: string
  note: string | null
}

/** Shown once a payment method is ticked Joint, to household members (the pot is the household's). */
export function jointAvailable(
  methods: { is_joint?: boolean }[] | null | undefined,
  household: HouseholdMember[] | null | undefined,
  myId: number | null,
): boolean {
  const inHousehold = (household ?? []).some((m) => m.user_id === myId)
  return inHousehold && (methods ?? []).some((m) => !!m.is_joint)
}

/** The two cumulative lines, as { x: day, y: cents } points; a line is empty when the API sent nothing for it. */
export function paceSeries(status: JointStatus): { thisMonth: { x: number; y: number }[]; usual: { x: number; y: number }[] } {
  const thisMonth: { x: number; y: number }[] = []
  const usual: { x: number; y: number }[] = []
  for (const d of status.days) {
    if (d.this_month !== null && d.this_month !== undefined) thisMonth.push({ x: d.day, y: cents(d.this_month) })
    if (d.usual !== null && d.usual !== undefined) usual.push({ x: d.day, y: cents(d.usual) })
  }
  return { thisMonth, usual }
}

/** This month so far minus the usual month by the same day (cents), or null without history. */
export function paceGap(status: JointStatus): number | null {
  if (status.usual_to_day === null || status.usual_to_day === undefined) return null
  return cents(status.spent_to_day) - cents(status.usual_to_day)
}

export function paceSentence(status: JointStatus): string {
  const day = ordinal(status.as_of_day)
  const spent = formatBrl(cents(status.spent_to_day))
  const gap = paceGap(status)
  if (gap === null) {
    return `By the ${day} you've spent ${spent}. Not enough history yet: the usual pace needs at least ` +
      'one full month of spending on this account.'
  }
  const usual = formatBrl(cents(status.usual_to_day))
  if (gap > 0) return `By the ${day} you've spent ${spent}, ▲ ${formatBrl(gap)} more than usual by now (${usual}).`
  if (gap < 0) return `By the ${day} you've spent ${spent}, ▼ ${formatBrl(-gap)} less than usual by now (${usual}).`
  return `By the ${day} you've spent ${spent}, right on the usual pace.`
}

/** 'At this pace the money lasts until 20 December.', or null when it can't be said. */
export function runOutText(status: Pick<JointStatus, 'balance' | 'runs_out_on' | 'month'>): string | null {
  if (status.balance === null || status.balance === undefined) return null
  if (cents(status.balance) <= 0) return 'The account is empty.'
  if (!status.runs_out_on) return "Nothing spent yet this month, so there's no pace to go by."
  const runsOut = status.runs_out_on.slice(0, 7)
  if (runsOut > status.month) return 'At this pace the money lasts past the end of the month.'
  return `At this pace the money lasts until ${Number(status.runs_out_on.slice(8, 10))} ${monthName(runsOut)}.`
}

/** "dd/mm/yyyy" of a timestamp in São Paulo. */
export function brDate(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return new Intl.DateTimeFormat('pt-BR', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' }).format(d)
}

export function countedFromText(status: Pick<JointStatus, 'balance' | 'counted_from'>): string {
  if (status.balance === null || status.balance === undefined) return 'Enter the balance your bank shows to start.'
  if (status.counted_from) {
    return `From the balance you entered on ${brDate(status.counted_from)}, plus deposits, minus spending since.`
  }
  return "From your first deposit, minus spending since. Enter the bank's balance to correct it."
}

/** The three KPI cards' contents: [label, value, lines]. */
export function jointCards(status: JointStatus): [string, string, [string, string | null][]][] {
  const gap = paceGap(status)
  const spentLines: [string, string | null][] = []
  if (gap !== null) {
    spentLines.push([`${gap > 0 ? '▲' : gap < 0 ? '▼' : ''} ${signedBrl(gap)} vs usual`.trim(),
      gap > 0 ? 'more' : gap < 0 ? 'less' : null])
  }
  spentLines.push([status.usual_month_total !== null && status.usual_month_total !== undefined
    ? `A usual month: ${formatBrl(cents(status.usual_month_total))}` : 'No usual month yet', null])
  const runsOut = status.runs_out_on
  return [
    ['Left in the account', status.balance !== null && status.balance !== undefined ? formatBrl(cents(status.balance)) : '–',
      [[countedFromText(status), null]]],
    ['Spent this month', formatBrl(cents(status.spent_to_day)), spentLines],
    ['Runs out', runsOut ? `${runsOut.slice(8, 10)}/${runsOut.slice(5, 7)}` : '–',
      [[runOutText(status) ?? 'Needs the balance first.', null]]],
  ]
}
