/**
 * What's still to come this month, from the expenses already logged (GET
 * /expenditures/): recurring bills seen in recent months that haven't shown
 * up yet this month, and card installments of earlier purchases billed this
 * month. The analytics count an installment purchase in full in the month
 * it was bought, so these say what this month's cash still has to cover.
 * Port of upcoming.py; amounts in cents.
 */
import { addMonths, dayOf, ordinal } from '../dates'
import { cents, shortBrl } from '../money'
import type { Lens } from './shaping'

export const LOOKBACK = 3 // months searched for a recurring bill

export interface Expense {
  expenditure_id: number
  transaction_timestamp: string
  price: string | number
  my_share?: string | number | null
  nature?: string | null
  is_shared?: boolean
  current_installment?: number | null
  total_installments?: number | null
  category?: { primary_category?: string; sub_category?: string; cost_type?: string } | null
}

export interface DueItem {
  name: string
  amount: number
  share: number
  text: string
  primary_category: string
  cost_type: string
  nature: string
  day: number
}

/** Whether an expense belongs to what's shown: "shared", "personal", or "all" (both). */
export function inView(e: Expense, view: string): boolean {
  if (view === 'shared') return !!e.is_shared
  if (view === 'personal') return !e.is_shared
  return true
}

/** The full price for the Household lens, else my part (a personal expense's is its price). */
export function amount(e: Expense, lens: Lens): number {
  return cents(lens === 'Household' ? e.price : (e.my_share ?? 0))
}

const what = (e: Expense) => `${e.category?.primary_category ?? '—'} › ${e.category?.sub_category ?? '—'}`

function finish(rows: Omit<DueItem, 'share'>[]): DueItem[] {
  const total = rows.reduce((a, r) => a + r.amount, 0)
  return rows.sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name))
    .map((r) => ({ ...r, share: total ? r.amount / total : 0 }))
}

/**
 * Recurring bills (nature "Recurring") logged in the LOOKBACK months before
 * `month` whose category hasn't been logged yet in `month`, each at its
 * latest amount and day, e.g. "R$ 180 · usually the 10th".
 */
export function recurringDue(expenses: Expense[] | null | undefined, month: string, view: string, lens: Lens): DueItem[] {
  const earlier = new Set(Array.from({ length: LOOKBACK }, (_, k) => addMonths(month, -(k + 1))))
  const seenNow = new Set<string>()
  const latest = new Map<string, { at: number; day: string; e: Expense }>()
  for (const e of expenses ?? []) {
    if (!inView(e, view)) continue
    const day = dayOf(e.transaction_timestamp)
    const m = day.slice(0, 7)
    const name = what(e)
    if (m === month) seenNow.add(name)
    else if (earlier.has(m) && e.nature === 'Recurring') {
      const at = new Date(e.transaction_timestamp).getTime()
      const prev = latest.get(name)
      if (!prev || at > prev.at) latest.set(name, { at, day, e })
    }
  }
  const rows: Omit<DueItem, 'share'>[] = []
  for (const [name, { day, e }] of latest) {
    if (seenNow.has(name)) continue
    const value = amount(e, lens)
    if (value <= 0) continue
    const d = Number(day.slice(8, 10))
    rows.push({ name, amount: value, text: `${shortBrl(value)} · usually the ${ordinal(d)}`,
      primary_category: e.category?.primary_category ?? '—', cost_type: e.category?.cost_type ?? 'Unknown',
      nature: 'Recurring', day: d })
  }
  return finish(rows)
}

/**
 * Card installments of purchases from earlier months billed in `month`: the
 * price split evenly, all but the last rounded down to the cent (as the
 * ETL's cashflow), e.g. "R$ 250 · 4 of 10".
 */
export function installmentsDue(expenses: Expense[] | null | undefined, month: string, view: string, lens: Lens): DueItem[] {
  const target = Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7))
  const rows: Omit<DueItem, 'share'>[] = []
  for (const e of expenses ?? []) {
    const total = e.total_installments || 1
    if (total <= 1 || !inView(e, view)) continue
    const day = dayOf(e.transaction_timestamp)
    const after = target - (Number(day.slice(0, 4)) * 12 + Number(day.slice(5, 7)))
    const number = (e.current_installment || 1) + after
    if (after <= 0 || number > total) continue // bought this month (already counted) or paid off
    const whole = amount(e, lens)
    const each = Math.floor(whole / total)
    const value = number === total ? whole - each * (total - 1) : each
    if (value <= 0) continue
    rows.push({ name: `${what(e)} · ${day.slice(8, 10)}/${day.slice(5, 7)}`, amount: value,
      text: `${shortBrl(value)} · ${number} of ${total}`,
      primary_category: e.category?.primary_category ?? '—', cost_type: e.category?.cost_type ?? 'Unknown',
      nature: e.nature || 'Normal', day: Number(day.slice(8, 10)) })
  }
  return finish(rows)
}
