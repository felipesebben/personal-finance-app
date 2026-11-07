/**
 * The Entries page's shaping: every expense you can see (GET /expenditures/)
 * as rows to audit, its filters, the trace of each edit, Add expense's
 * "Log again" templates, and an expense's values for the edit form.
 * Port of the Streamlit frontend's entries.py; tests in entries.test.ts.
 */
import { TZ } from './dates'
import { cents, formatBrl } from './money'

/** How a payment method stored without an institution is shown and matched. */
export const NO_INSTITUTION = 'N/A'
/** A pet-category expense with no pet_id was for all the pets. */
export const ALL_PETS = 'Both'
export const KINDS: Record<string, string> = { all: 'Everything', shared: 'Shared', personal: 'Personal' }

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December']

export interface UserRef { user_id: number; full_name?: string | null; email?: string | null }
export interface CategoryRef {
  category_id?: number
  primary_category: string
  sub_category: string
  cost_type?: string
  for_pets?: boolean
}
export interface MethodRef {
  payment_method_id?: number
  method_name: string
  institution?: string | null
  is_credit?: boolean
  is_joint?: boolean
}
export interface PetRef { pet_id: number; name: string }
export interface SplitRef { user_id: number; share_pct: string; share_amount?: string; split_source?: string }

/** An expense as GET /expenditures/ returns it (ExpenditureRead). */
export interface Expense {
  expenditure_id: number
  transaction_timestamp: string
  price: string
  nature?: string | null
  is_shared?: boolean
  my_share?: string | null
  is_treat?: boolean
  current_installment?: number | null
  total_installments?: number | null
  user?: UserRef | null
  category?: CategoryRef | null
  payment_method?: MethodRef | null
  pet?: PetRef | null
  splits?: SplitRef[]
  updated_at?: string | null
  updated_by?: UserRef | null
}

export interface LocalTime {
  day: string // YYYY-MM-DD
  time: string // HH:MM
  month: string // YYYY-MM
  epoch: number
}

const PARTS = new Intl.DateTimeFormat('en-CA', {
  timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** An API timestamp in São Paulo time (a naive one is UTC). */
export function local(iso: string): LocalTime {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  const p = Object.fromEntries(PARTS.formatToParts(d).map((x) => [x.type, x.value]))
  const day = `${p.year}-${p.month}-${p.day}`
  return { day, time: `${p.hour}:${p.minute}`, month: day.slice(0, 7), epoch: d.getTime() }
}

/** "05/10/2026" */
export function dmy(day: string): string {
  return `${day.slice(8, 10)}/${day.slice(5, 7)}/${day.slice(0, 4)}`
}

/** "3 August 2026" (or "3 August" without the year). */
export function longDay(day: string, year = true): string {
  const text = `${Number(day.slice(8, 10))} ${MONTHS[Number(day.slice(5, 7)) - 1]}`
  return year ? `${text} ${day.slice(0, 4)}` : text
}

export function nameOf(user: UserRef | null | undefined): string {
  return user?.full_name || user?.email || '—'
}

/** 'Shared', 'Personal', 'Shared · treat', 'Shared · 10x'. */
export function kindText(e: Expense): string {
  let text = e.is_shared ? 'Shared' : 'Personal'
  if (e.is_treat) text += ' · treat'
  const total = e.total_installments || 1
  return total > 1 ? `${text} · ${total}x` : text
}

/** 'Food · Groceries', and the pet for a pet category: 'Pets · Vet · Thor' (or '· Both'). */
export function whatText(e: Expense): string {
  const c = e.category
  let text = `${c?.primary_category ?? '—'} · ${c?.sub_category ?? '—'}`
  if (c?.for_pets) text += ` · ${e.pet?.name || ALL_PETS}`
  return text
}

export function paidWith(e: Expense): string {
  const m = e.payment_method
  const name = m?.method_name ?? '—'
  return m?.institution ? `${name} · ${m.institution}` : name
}

/** 'Her · 18/10 14:02' for the last edit, '' when never edited. */
export function editText(e: Expense): string {
  if (!e.updated_at) return ''
  const when = local(e.updated_at)
  const who = e.updated_by ? nameOf(e.updated_by) : 'a deleted account'
  return `${who} · ${when.day.slice(8, 10)}/${when.day.slice(5, 7)} ${when.time}`
}

/** Who logged it, and who last changed it and when, in a sentence. */
export function traceText(e: Expense): string {
  const logged = `Logged by ${nameOf(e.user)}.`
  if (!e.updated_at) return `${logged} Never edited.`
  const when = local(e.updated_at)
  const who = e.updated_by ? nameOf(e.updated_by) : 'an account since deleted'
  return `${logged} Last edited by ${who} on ${longDay(when.day, false)} at ${when.time}.`
}

export interface EntryRow {
  id: number
  epoch: number
  month: string
  kind: 'shared' | 'personal'
  primary: string
  loggedBy: string
  priceCents: number
  mineCents: number
  when: string
  what: string
  price: string
  yourPart: string
  paidWith: string
  type: string
  lastEdit: string
}

/** One row per expense, newest first: the display texts plus what the filters read. */
export function entryRows(expenses: Expense[] | null | undefined): EntryRow[] {
  return (expenses ?? []).map((e) => {
    const when = local(e.transaction_timestamp)
    return {
      id: e.expenditure_id,
      epoch: when.epoch,
      month: when.month,
      kind: e.is_shared ? 'shared' : 'personal',
      primary: e.category?.primary_category ?? '—',
      loggedBy: nameOf(e.user),
      priceCents: cents(e.price),
      mineCents: cents(e.my_share ?? 0),
      when: `${dmy(when.day)} ${when.time}`,
      what: whatText(e),
      price: formatBrl(cents(e.price)),
      yourPart: formatBrl(cents(e.my_share ?? 0)),
      paidWith: paidWith(e),
      type: kindText(e),
      lastEdit: editText(e),
    } satisfies EntryRow
  }).sort((a, b) => b.epoch - a.epoch || b.id - a.id)
}

export interface EntryFilters {
  month?: string | null
  kind?: string
  loggedBy?: string | null
  categories?: string[]
  search?: string
}

/** The rows matching every filter given; `search` looks in what, how it was paid and the price. */
export function filterEntries(rows: EntryRow[], f: EntryFilters = {}): EntryRow[] {
  const text = (f.search ?? '').trim().toLowerCase()
  return rows.filter((r) =>
    (!f.month || r.month === f.month) &&
    (!f.kind || f.kind === 'all' || r.kind === f.kind) &&
    (!f.loggedBy || r.loggedBy === f.loggedBy) &&
    (!f.categories?.length || f.categories.includes(r.primary)) &&
    (!text || `${r.what} ${r.paidWith} ${r.price}`.toLowerCase().includes(text)))
}

/** '12 expenses · R$ 1.234,00 · your part R$ 700,00'. */
export function summary(rows: EntryRow[]): string {
  const n = rows.length
  const price = rows.reduce((s, r) => s + r.priceCents, 0)
  const mine = rows.reduce((s, r) => s + r.mineCents, 0)
  return `${n} ${n === 1 ? 'expense' : 'expenses'} · ${formatBrl(price)} · your part ${formatBrl(mine)}`
}

/** What a recent expense is called in Add expense's "Log again" row: "Groceries · Debit Card · Nubank". */
export function templateLabel(e: Expense): string {
  const c = e.category
  let what = c?.sub_category || c?.primary_category || '—'
  if (c?.for_pets && e.pet) what += ` · ${e.pet.name}`
  const text = `${what} · ${paidWith(e)}`
  return e.is_shared ? text : `${text} · just me`
}

/**
 * The last `n` different things I logged, newest first, as [label, expense]:
 * what Add expense offers to log again. Different = a different label (what,
 * how it was paid, shared or just me); only my own entries.
 */
export function recentTemplates(expenses: Expense[] | null | undefined, myUserId: number | null, n = 6):
  [string, Expense][] {
  const mine = (expenses ?? []).filter((e) => e.user?.user_id === myUserId)
    .map((e) => ({ e, at: local(e.transaction_timestamp).epoch }))
    .sort((a, b) => b.at - a.at || b.e.expenditure_id - a.e.expenditure_id)
  const out = new Map<string, Expense>()
  for (const { e } of mine) {
    const label = templateLabel(e)
    if (!out.has(label)) out.set(label, e)
    if (out.size === n) break
  }
  return [...out]
}

export interface FormValues {
  priceText: string
  method: string | null
  institution: string
  totalInstallments: number
  currentInstallment: number
  primary: string | null
  sub: string | null
  /** A pet name or ALL_PETS, only when the form asks (two or more pets). */
  pet: string | null
  shared: boolean
  wasShared: boolean
  treat: boolean
  /** {user_id: percent} for a manual split, else null. */
  custom: Record<number, number> | null
  /** The stored [user_id, share fraction] pairs. */
  split: [number, number][]
  splitText: string
  nature: string
  date: string
  time: string
}

/** An expense from GET /expenditures/ as the edit form's starting values. */
export function formValues(e: Expense, pets: PetRef[] | null | undefined, names: Record<number, string> = {}): FormValues {
  const when = local(e.transaction_timestamp)
  const m = e.payment_method
  const c = e.category
  const splits = e.splits ?? []
  let pet: string | null = null
  if (c?.for_pets && (pets?.length ?? 0) > 1) pet = e.pet?.name || ALL_PETS
  const manual = splits.some((s) => s.split_source === 'manual')
  const split: [number, number][] = splits.map((s) => [s.user_id, Number(s.share_pct)])
  return {
    priceText: formatBrl(cents(e.price), false),
    method: m?.method_name ?? null,
    institution: m?.institution || NO_INSTITUTION,
    totalInstallments: e.total_installments || 1,
    currentInstallment: e.current_installment || 1,
    primary: c?.primary_category ?? null,
    sub: c?.sub_category ?? null,
    pet,
    shared: !!e.is_shared,
    wasShared: !!e.is_shared,
    treat: !!e.is_treat,
    custom: manual ? Object.fromEntries(split.map(([uid, pct]) => [uid, Math.round(pct * 100)])) : null,
    split,
    splitText: split.map(([uid, pct]) => `${names[uid] ?? `user ${uid}`} ${Math.round(pct * 100)}%`).join(' · '),
    nature: e.nature || 'Normal',
    date: when.day,
    time: when.time,
  }
}
