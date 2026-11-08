import { describe, expect, it } from 'vitest'
import {
  ALL_PETS, NO_INSTITUTION, entryRows, filterEntries, formValues, recentTemplates, summary, traceText, whatText,
  type Expense,
} from './entries'
import { backfillLines, duplicateLines } from './entryChecks'
import { fillRest } from './shares'

const ME = { user_id: 1, full_name: 'Me', email: 'me@example.com' }
const HER = { user_id: 2, full_name: 'Her', email: 'her@example.com' }
const FOOD = { primary_category: 'Food', sub_category: 'Groceries', for_pets: false }
const VET = { primary_category: 'Pets', sub_category: 'Vet', for_pets: true }
const NUBANK = { method_name: 'Credit Card', institution: 'Nubank' }
const PIX = { method_name: 'Pix', institution: null }

function expense(eid = 1, when = '2026-10-05T15:30:00+00:00', price = '100.00', extra: Partial<Expense> = {}): Expense {
  return {
    expenditure_id: eid, transaction_timestamp: when, price, nature: 'Normal', is_shared: true, my_share: '60.00',
    is_treat: false, total_installments: 1, current_installment: 1, user: ME, category: FOOD, payment_method: NUBANK,
    pet: null,
    splits: [
      { user_id: 1, share_pct: '0.6000', share_amount: '60.00', split_source: 'household_default' },
      { user_id: 2, share_pct: '0.4000', share_amount: '40.00', split_source: 'household_default' },
    ],
    updated_at: null, updated_by: null, ...extra,
  }
}

describe('entries', () => {
  it('reads newest first in São Paulo time', () => {
    const rows = entryRows([expense(1), expense(2, '2026-10-01T01:00:00+00:00', '100.00', { payment_method: PIX })])
    expect(rows.map((r) => r.id)).toEqual([1, 2])
    expect(rows.map((r) => r.when)).toEqual(['05/10/2026 12:30', '30/09/2026 22:00'])
    expect(rows.map((r) => r.month)).toEqual(['2026-10', '2026-09'])
    expect(rows.map((r) => r.paidWith)).toEqual(['Credit Card · Nubank', 'Pix'])
    expect(rows.map((r) => r.price)).toEqual(['R$ 100,00', 'R$ 100,00'])
  })

  it('shows types, pets and the last edit', () => {
    const e = expense(1, undefined, undefined, {
      category: VET, pet: { pet_id: 7, name: 'Thor' }, total_installments: 10, is_treat: true,
      updated_at: '2026-10-18T17:02:00+00:00', updated_by: HER,
    })
    const [row] = entryRows([e])
    expect(row.what).toBe('Pets · Vet · Thor')
    expect(row.type).toBe('Shared · treat · 10x')
    expect(row.lastEdit).toBe('Her · 18/10 14:02')
    expect(whatText(expense(1, undefined, undefined, { category: VET }))).toBe('Pets · Vet · Both')
    expect(entryRows([expense()])[0].lastEdit).toBe('')
  })

  it('writes the trace in words', () => {
    expect(traceText(expense())).toBe('Logged by Me. Never edited.')
    const edited = expense(1, undefined, undefined, { updated_at: '2026-10-18T17:02:00+00:00', updated_by: HER })
    expect(traceText(edited)).toBe('Logged by Me. Last edited by Her on 18 October at 14:02.')
    const gone = expense(1, undefined, undefined, { updated_at: '2026-10-18T17:02:00+00:00', updated_by: null })
    expect(traceText(gone)).toContain('an account since deleted')
  })

  it('combines filters', () => {
    const rows = entryRows([
      expense(1),
      expense(2, '2026-10-04T15:30:00+00:00', '45.90', { is_shared: false, user: HER, payment_method: PIX }),
      expense(3, '2026-09-05T15:30:00+00:00', '100.00', { category: VET }),
    ])
    const ids = (f: Parameters<typeof filterEntries>[1]) => filterEntries(rows, f).map((r) => r.id)
    expect(ids({ month: '2026-10' })).toEqual([1, 2])
    expect(ids({ kind: 'personal' })).toEqual([2])
    expect(ids({ loggedBy: 'Her' })).toEqual([2])
    expect(ids({ categories: ['Pets'] })).toEqual([3])
    expect(ids({ search: '45,90' })).toEqual([2])
    expect(ids({ search: 'nubank' })).toEqual([1, 3])
    expect(ids({ month: '2026-10', categories: ['Pets'] })).toEqual([])
  })

  it('sums up', () => {
    expect(summary(entryRows([expense(1), expense(2)]))).toBe('2 expenses · R$ 200,00 · your part R$ 120,00')
  })

  it('fills the edit form', () => {
    const e = expense(1, undefined, '1234.56', { total_installments: 10, current_installment: 4, nature: 'Annual' })
    const v = formValues(e, [], { 1: 'Me', 2: 'Her' })
    expect(v.priceText).toBe('1.234,56')
    expect([v.method, v.institution]).toEqual(['Credit Card', 'Nubank'])
    expect([v.totalInstallments, v.currentInstallment]).toEqual([10, 4])
    expect([v.primary, v.sub, v.nature]).toEqual(['Food', 'Groceries', 'Annual'])
    expect(v.shared).toBe(true)
    expect(v.custom).toBeNull()
    expect(v.split).toEqual([[1, 0.6], [2, 0.4]])
    expect(v.splitText).toBe('Me 60% · Her 40%')
    expect([v.date, v.time]).toEqual(['2026-10-05', '12:30'])
  })

  it('fills a manual split, a pet and no institution', () => {
    const manual = [
      { user_id: 1, share_pct: '0.3000', share_amount: '30.00', split_source: 'manual' },
      { user_id: 2, share_pct: '0.7000', share_amount: '70.00', split_source: 'manual' },
    ]
    const twoPets = [{ pet_id: 7, name: 'Thor' }, { pet_id: 8, name: 'Luna' }]
    const v = formValues(expense(1, undefined, undefined, { splits: manual, category: VET, payment_method: PIX }), twoPets)
    expect(v.custom).toEqual({ 1: 30, 2: 70 })
    expect(v.pet).toBe(ALL_PETS)
    expect(v.institution).toBe(NO_INSTITUTION)
    expect(formValues(expense(1, undefined, undefined, { category: VET }), twoPets.slice(0, 1)).pet).toBeNull()
  })

  it('offers my last different expenses to log again, newest first', () => {
    const logged = [
      expense(1, '2026-10-01T12:00:00+00:00'),
      expense(2, '2026-10-05T12:00:00+00:00', '80.00'),
      expense(3, '2026-10-03T12:00:00+00:00', '100.00', { payment_method: PIX, is_shared: false }),
      expense(4, '2026-10-06T12:00:00+00:00', '100.00', { user: HER }),
    ]
    const templates = recentTemplates(logged, 1)
    expect(templates.map(([l]) => l)).toEqual(['Groceries · Credit Card · Nubank', 'Groceries · Pix · just me'])
    expect(templates[0][1].expenditure_id).toBe(2)
    expect(recentTemplates(logged, 1, 1)).toEqual(templates.slice(0, 1))
    expect(recentTemplates([], 1)).toEqual([])
  })
})

describe('entryChecks', () => {
  it('says who logged a duplicate', () => {
    expect(duplicateLines([
      { logged_by: 'Me', logged_by_me: true, transaction_timestamp: '2026-09-05T15:30:00+00:00', price: '85.00',
        category: 'Food › Eating Out', payment_method: 'Pix · Nubank' },
      { logged_by: 'Lívia', logged_by_me: false, transaction_timestamp: '2026-09-06T02:30:00+00:00', price: '85.00',
        category: 'Food › Eating Out', payment_method: 'Credit Card · Itaú' },
    ])).toEqual([
      'You already logged this on 05/09/2026: R$ 85,00 · Food › Eating Out · Pix · Nubank.',
      'Lívia already logged a matching shared expense on 05/09/2026: R$ 85,00 · Food › Eating Out · Credit Card · Itaú.',
    ])
  })

  const e = (when: string, price: string, userId: number, shared: boolean, primary = 'Food', sub = 'Groceries'): Expense => ({
    expenditure_id: 0, transaction_timestamp: when, price, is_shared: shared,
    user: { user_id: userId, full_name: userId === 1 ? 'Me' : 'Lívia' },
    category: { primary_category: primary, sub_category: sub },
  })

  it('names who logged shared, and personal is only mine', () => {
    expect(backfillLines([
      e('2026-10-02T12:00:00+00:00', '40.00', 2, true),
      e('2026-08-03T12:00:00+00:00', '450.00', 1, true, 'Housing', 'Cleaning'),
      e('2026-08-20T12:00:00+00:00', '12.50', 1, true),
      e('2026-09-10T12:00:00+00:00', '30.00', 1, false, 'Health', 'Pharmacy'),
      e('2026-09-25T12:00:00+00:00', '99.00', 1, false),
    ], 1)).toEqual([
      'Shared: earliest 3 August 2026 (R$ 450,00 · Housing › Cleaning · logged by you), '
        + 'latest 2 October 2026 (R$ 40,00 · Food › Groceries · logged by Lívia). By month: Aug 2026 2 · Oct 2026 1.',
      'Personal: earliest 10 September 2026 (R$ 30,00 · Health › Pharmacy), '
        + 'latest 25 September 2026 (R$ 99,00 · Food › Groceries). By month: Sep 2026 2.',
    ])
  })

  it('says a single expense once, and nothing without any', () => {
    expect(backfillLines([e('2026-08-03T12:00:00+00:00', '85.00', 2, true)], 1)).toEqual([
      'Shared: one so far, 3 August 2026 (R$ 85,00 · Food › Groceries · logged by Lívia).',
    ])
    expect(backfillLines([], 1)).toEqual([])
    expect(backfillLines([e('2026-08-03T12:00:00+00:00', '85.00', 2, false)], 1)).toEqual([])
  })
})

describe('fillRest', () => {
  it('gives the other person the rest', () => {
    expect(fillRest({ 1: 50, 2: 20 }, 1)).toEqual({ 1: 50, 2: 50 })
    expect(fillRest({ 1: 80, 2: 0 }, 2)).toEqual({ 1: 100, 2: 0 })
  })
  it('never goes below zero', () => {
    expect(fillRest({ 1: 100, 2: 5 }, 1)).toEqual({ 1: 100, 2: 0 })
  })
  it('with more people, the one other who shares', () => {
    expect(fillRest({ 1: 50, 2: 80, 3: 0 }, 1)).toEqual({ 1: 50, 2: 50, 3: 0 })
  })
  it('changes nothing without a single other person', () => {
    expect(fillRest({ 1: 50, 2: 30, 3: 20 }, 1)).toEqual({ 1: 50, 2: 30, 3: 20 })
    expect(fillRest({ 1: 70, 2: 0, 3: 0 }, 1)).toEqual({ 1: 70, 2: 0, 3: 0 })
    expect(fillRest({ 1: 40 }, 1)).toEqual({ 1: 40 })
  })
})
