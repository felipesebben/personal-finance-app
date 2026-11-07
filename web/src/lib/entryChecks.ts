/**
 * Add expense's checks: the duplicate warning's sentences and the "where am I
 * with backfilling" lines. Port of entry_checks.py; tests in entryChecks.test.ts.
 */
import { dmy, local, longDay, type Expense } from './entries'
import { cents, formatBrl } from './money'

const SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** One expense the API says the new one may duplicate (the 409's detail.duplicates). */
export interface Duplicate {
  expenditure_id?: number
  logged_by?: string | null
  logged_by_me?: boolean
  transaction_timestamp: string
  price: string
  category?: string | null
  payment_method?: string | null
}

/** One sentence per expense the API says this one may duplicate. */
export function duplicateLines(duplicates: Duplicate[]): string[] {
  return duplicates.map((d) => {
    const day = dmy(local(d.transaction_timestamp).day)
    const what = [formatBrl(cents(d.price)), d.category, d.payment_method].filter(Boolean).join(' · ')
    const who = d.logged_by_me ? 'You already logged this'
      : `${d.logged_by || 'Your partner'} already logged a matching shared expense`
    return `${who} on ${day}: ${what}.`
  })
}

function describe(e: Expense, day: string, loggedBy?: string): string {
  const c = e.category
  const parts = [
    formatBrl(cents(e.price)),
    c ? `${c.primary_category} › ${c.sub_category}` : null,
    loggedBy ? `logged by ${loggedBy}` : null,
  ].filter(Boolean)
  return `${longDay(day)} (${parts.join(' · ')})`
}

function spanLine(label: string, expenses: Expense[], who?: (e: Expense) => string): string | null {
  if (!expenses.length) return null
  const when = expenses.map((e) => local(e.transaction_timestamp))
  let first = 0
  let last = 0
  when.forEach((w, i) => {
    if (w.epoch < when[first].epoch) first = i
    if (w.epoch > when[last].epoch) last = i
  })
  const counts = new Map<string, number>()
  for (const w of when) counts.set(w.month, (counts.get(w.month) ?? 0) + 1)
  const byMonth = [...counts].sort(([a], [b]) => a.localeCompare(b))
    .map(([m, n]) => `${SHORT[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)} ${n}`).join(' · ')
  const earliest = describe(expenses[first], when[first].day, who?.(expenses[first]))
  if (first === last) return `${label}: one so far, ${earliest}.`
  const latest = describe(expenses[last], when[last].day, who?.(expenses[last]))
  return `${label}: earliest ${earliest}, latest ${latest}. By month: ${byMonth}.`
}

/**
 * Where logging has got to, to see where backfilling stopped: the earliest and
 * latest shared expense (saying who logged each) and the earliest and latest
 * of my personal ones, with counts per month. Only what I can see.
 */
export function backfillLines(expenses: Expense[] | null | undefined, myUserId: number | null): string[] {
  const loggedBy = (e: Expense) => e.user?.user_id === myUserId ? 'you' : (e.user?.full_name || 'your partner')
  const all = expenses ?? []
  const shared = all.filter((e) => e.is_shared)
  const personal = all.filter((e) => !e.is_shared && e.user?.user_id === myUserId)
  return [spanLine('Shared', shared, loggedBy), spanLine('Personal', personal)].filter((l): l is string => !!l)
}
