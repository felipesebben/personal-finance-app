import { describe, expect, it } from 'vitest'
import { formValues, type Expense } from './entries'
import { createPayload, editPayload, missingFields, type FormState } from './entryPayload'

const categories = [
  { category_id: 10, primary_category: 'Food', sub_category: 'Groceries', for_pets: false },
  { category_id: 11, primary_category: 'Pets', sub_category: 'Vet', for_pets: true },
]
const methods = [
  { payment_method_id: 20, method_name: 'Credit Card', institution: 'Nubank', is_credit: true },
  { payment_method_id: 21, method_name: 'Cash', institution: null },
]

const state = (extra: Partial<FormState> = {}): FormState => ({
  price: 4590, priceError: '', method: 'Credit Card', institution: 'Nubank', totalInstallments: 1,
  currentInstallment: 1, primary: 'Food', sub: 'Groceries', petId: null, petMissing: false, shared: true,
  treat: false, customShares: null, nature: 'Normal', date: '2026-11-07', time: '14:05', ...extra,
})

const logged: Expense = {
  expenditure_id: 5, transaction_timestamp: '2026-11-07T17:05:00+00:00', price: '45.90', nature: 'Normal',
  is_shared: true, is_treat: false, total_installments: 1, current_installment: 1,
  user: { user_id: 1, full_name: 'Me' }, category: categories[0], payment_method: methods[0], pet: null,
  splits: [
    { user_id: 1, share_pct: '0.6000', split_source: 'household_default' },
    { user_id: 2, share_pct: '0.4000', split_source: 'household_default' },
  ],
}

describe('missingFields', () => {
  it('lists what is missing', () => {
    expect(missingFields(state())).toEqual([])
    expect(missingFields(state({ price: null, priceError: 'Use at most two digits for cents', sub: '' })))
      .toEqual(['Price (Use at most two digits for cents)', 'Sub-category'])
    expect(missingFields(state({ customShares: [[1, 60], [2, 30]] }))).toEqual(['Custom split (must add up to 100%)'])
  })
})

describe('createPayload', () => {
  it('builds the POST body in São Paulo time with the price as a string', () => {
    expect(createPayload(state(), categories, methods)).toEqual({
      transaction_timestamp: '2026-11-07T14:05:00-03:00', price: '45.90', category_id: 10, payment_method_id: 20,
      nature: 'Normal', is_shared: true, is_treat: false, current_installment: 1, total_installments: 1, user_id: 0,
    })
  })
  it('matches a method without an institution and drops 0% shares', () => {
    const p = createPayload(state({ method: 'Cash', institution: 'N/A', customShares: [[1, 100], [2, 0]], petId: 3 }),
      categories, methods)
    expect(p.payment_method_id).toBe(21)
    expect(p.shares).toEqual([{ user_id: 1, share_pct: '1.00' }])
    expect(p.pet_id).toBe(3)
  })
  it('a treat only when shared', () => {
    expect(createPayload(state({ shared: false, treat: true }), categories, methods).is_treat).toBe(false)
  })
})

describe('editPayload', () => {
  const original = formValues(logged, [])
  it('sends nothing when nothing changed', () => {
    expect(editPayload(state(), logged, original, categories, methods)).toEqual({})
  })
  it('sends only what changed', () => {
    expect(editPayload(state({ price: 5000, nature: 'Annual' }), logged, original, categories, methods))
      .toEqual({ price: '50.00', nature: 'Annual' })
    expect(editPayload(state({ totalInstallments: 3, currentInstallment: 1 }), logged, original, categories, methods))
      .toEqual({ total_installments: 3, current_installment: 1 })
    expect(editPayload(state({ shared: false }), logged, original, categories, methods)).toEqual({ is_shared: false })
  })
  it('sends a new custom split, and resets one that was unticked', () => {
    expect(editPayload(state({ customShares: [[1, 70], [2, 30]] }), logged, original, categories, methods))
      .toEqual({ shares: [{ user_id: 1, share_pct: '0.70' }, { user_id: 2, share_pct: '0.30' }] })
    const manual = { ...logged, splits: logged.splits!.map((s) => ({ ...s, split_source: 'manual' })) }
    const o = formValues(manual, [])
    expect(editPayload(state({ customShares: [[1, 60], [2, 40]] }), manual, o, categories, methods)).toEqual({})
    expect(editPayload(state(), manual, o, categories, methods)).toEqual({ reset_split: true })
  })
})
