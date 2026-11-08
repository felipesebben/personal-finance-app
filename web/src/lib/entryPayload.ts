/**
 * The expense form's request bodies, kept pure so they're tested:
 * what's missing before saving, the POST body for a new expense, and for an
 * edit only the fields that changed (PATCH /expenditures/{id}, which leaves
 * a trace only when something did).
 */
import { saoPauloTimestamp } from './dates'
import { NO_INSTITUTION, type CategoryRef, type Expense, type FormValues, type MethodRef } from './entries'
import { cents, toApi } from './money'

export interface FormState {
  price: number | null
  priceError: string
  method: string
  institution: string
  totalInstallments: number
  currentInstallment: number
  primary: string
  sub: string
  petId: number | null
  petMissing: boolean
  shared: boolean
  treat: boolean
  /** [user_id, percent] pairs when a custom split is on, else null. */
  customShares: [number, number][] | null
  nature: string
  date: string
  time: string
}

export type Payload = Record<string, unknown>

/** What still needs filling in, in words; empty when it can be saved. */
export function missingFields(s: FormState): string[] {
  const missing: string[] = []
  if (s.price === null) missing.push(s.priceError ? `Price (${s.priceError})` : 'Price')
  if (!s.method) missing.push('Payment method')
  if (!s.institution) missing.push('Institution')
  if (!s.primary) missing.push('Category')
  if (!s.sub) missing.push('Sub-category')
  if (s.petMissing) missing.push('Which pet')
  if (!s.nature) missing.push('Nature')
  if (!s.date || !s.time) missing.push('Date and time')
  if (s.customShares && s.customShares.reduce((t, [, p]) => t + p, 0) !== 100) {
    missing.push('Custom split (must add up to 100%)')
  }
  return missing
}

export function findMethod(methods: MethodRef[], method: string, institution: string): MethodRef | undefined {
  return methods.find((m) => m.method_name === method && (m.institution || NO_INSTITUTION) === institution)
}

export function findCategory(categories: CategoryRef[], primary: string, sub: string): CategoryRef | undefined {
  return categories.find((c) => c.primary_category === primary && c.sub_category === sub)
}

/** The fields both a new expense and an edit send (everything but user_id, pet and the split). */
export function basePayload(s: FormState, categories: CategoryRef[], methods: MethodRef[]): Payload {
  const method = findMethod(methods, s.method, s.institution)
  const category = findCategory(categories, s.primary, s.sub)
  if (!method?.payment_method_id || !category?.category_id) throw new Error('Pick the payment method and category again.')
  const payload: Payload = {
    transaction_timestamp: saoPauloTimestamp(s.date, s.time),
    price: toApi(s.price ?? 0),
    category_id: category.category_id,
    payment_method_id: method.payment_method_id,
    nature: s.nature,
    is_shared: s.shared,
    is_treat: s.shared && s.treat,
    current_installment: s.currentInstallment,
    total_installments: s.totalInstallments,
  }
  if (s.customShares) {
    // People at 0% simply bear none of it, so they get no row.
    payload.shares = s.customShares.filter(([, p]) => p > 0)
      .map(([user_id, p]) => ({ user_id, share_pct: (p / 100).toFixed(2) }))
  }
  return payload
}

/** POST /expenditures/: the API sets the payer from the token; the dummy user_id stays for compatibility. */
export function createPayload(s: FormState, categories: CategoryRef[], methods: MethodRef[]): Payload {
  const payload: Payload = { ...basePayload(s, categories, methods), user_id: 0 }
  if (s.petId !== null) payload.pet_id = s.petId
  return payload
}

const sameShares = (a: Record<number, number> | null, b: [number, number][]) =>
  !!a && Object.keys(a).length === b.filter(([, p]) => p > 0).length && b.every(([u, p]) => p === 0 || a[u] === p)

/**
 * PATCH /expenditures/{id}: only what differs from the expense as logged.
 * The split: a custom split is sent when it's new or changed; unticking a
 * custom split on a shared expense sends reset_split (today's household
 * ratio); otherwise a shared expense keeps the ratio it was logged with.
 * An empty object means nothing changed.
 */
export function editPayload(s: FormState, e: Expense, original: FormValues,
  categories: CategoryRef[], methods: MethodRef[]): Payload {
  const next = basePayload(s, categories, methods)
  const out: Payload = {}
  if (s.date !== original.date || s.time !== original.time) out.transaction_timestamp = next.transaction_timestamp
  if (s.price !== cents(e.price)) out.price = next.price
  if (next.category_id !== e.category?.category_id) out.category_id = next.category_id
  if (next.payment_method_id !== e.payment_method?.payment_method_id) out.payment_method_id = next.payment_method_id
  if (s.nature !== original.nature) out.nature = s.nature
  if (s.shared !== original.shared) out.is_shared = s.shared
  if (next.is_treat !== original.treat) out.is_treat = next.is_treat
  if (s.totalInstallments !== original.totalInstallments) out.total_installments = s.totalInstallments
  if (s.currentInstallment !== original.currentInstallment || 'total_installments' in out) {
    out.current_installment = s.currentInstallment
  }
  if (s.petId !== (e.pet?.pet_id ?? null)) out.pet_id = s.petId
  if (s.shared && s.customShares) {
    if (!original.shared || !sameShares(original.custom, s.customShares)) out.shares = next.shares
  } else if (s.shared && original.custom !== null) {
    out.reset_split = true
  }
  return out
}
