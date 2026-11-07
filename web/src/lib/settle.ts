/**
 * Settle up's words: who owes whom and the buttons in the viewer's own
 * voice. Port of the pure parts of frontend/sections/settle.py; tests in
 * settle.test.ts.
 */
import { cents, formatBrl } from './money'
import { monthLabel } from './dates'
import type { Transfer } from './briefing'

export interface MemberBalance {
  user_id: number
  full_name: string | null
  paid: string
  borne: string
  settled_out: string
  settled_in: string
  net: string
}

export interface BalanceReport {
  month: string | null
  members: MemberBalance[]
  transfers: Transfer[]
}

export interface Settlement {
  settlement_id: number
  settled_at: string
  month: string | null
  from_user_id: number
  from_name: string | null
  to_user_id: number
  to_name: string | null
  amount: string
  note: string | null
}

export const ALL_TIME = 'All time'

export function periodLabel(period: string): string {
  return period === ALL_TIME ? period : monthLabel(period)
}

/** 'Is owed R$ 120,00', 'Owes R$ 120,00' or 'Square'. */
export function netText(net: string | number): string {
  const value = cents(net)
  if (value === 0) return 'Square'
  return `${value > 0 ? 'Is owed' : 'Owes'} ${formatBrl(Math.abs(value))}`
}

/** What a person paid, their share, and any payments between you, as KPI lines. */
export function personLines(m: MemberBalance): [string, null][] {
  const lines: [string, null][] = [[`Paid ${formatBrl(cents(m.paid))}`, null], [`Their share ${formatBrl(cents(m.borne))}`, null]]
  if (cents(m.settled_out)) lines.push([`Paid back ${formatBrl(cents(m.settled_out))}`, null])
  if (cents(m.settled_in)) lines.push([`Received ${formatBrl(cents(m.settled_in))}`, null])
  return lines
}

/**
 * The settle buttons' words, from whoever is looking: the one who owes says
 * "I paid Felipe R$ 447,53", the one owed "Lívia paid me R$ 447,53", anyone
 * else "Lívia paid Felipe R$ 447,53".
 */
export function actionLabels(t: Transfer, me: number | null): { all: string; other: string } {
  const amount = formatBrl(cents(t.amount))
  const payer = t.from_name ?? 'Someone'
  const payee = t.to_name ?? 'someone'
  if (me === t.from_user_id) return { all: `I paid ${payee} ${amount}`, other: `I paid ${payee} a different amount` }
  if (me === t.to_user_id) return { all: `${payer} paid me ${amount}`, other: `${payer} paid me a different amount` }
  return { all: `${payer} paid ${payee} ${amount}`, other: `${payer} paid ${payee} a different amount` }
}
