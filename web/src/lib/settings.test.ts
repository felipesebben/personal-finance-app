import { describe, expect, it } from 'vitest'
import {
  CATEGORIES, PAYMENT_METHODS, PETS, fillRest, householdPayload, isEmptyPlan, planChanges, suggestTargets, targetRows,
  targetsPayload, type Row,
} from './settings'
import { addMonths } from './dates'
import type { AnalyticsPayload } from './briefing'

const CATS: Row[] = [
  { category_id: 1, primary_category: 'Food', sub_category: 'Groceries', cost_type: 'Variable', expense_count: 3 },
  { category_id: 2, primary_category: 'Leisure', sub_category: 'Streaming', cost_type: 'Fixed', expense_count: 0 },
]

function edited(changes: [number, Row][] = [], drop: number[] = [], add: Row[] = []): Row[] {
  const rows = CATS.filter((r) => !drop.includes(r.category_id as number)).map((r) => ({ ...r }))
  for (const [id, fields] of changes) Object.assign(rows.find((r) => r.category_id === id)!, fields)
  return [...rows, ...add.map((a) => ({ category_id: null, expense_count: null, ...a }))]
}

describe('planChanges', () => {
  it('plans nothing without edits', () => {
    const plan = planChanges(CATS, edited(), CATEGORIES)
    expect(isEmptyPlan(plan) && !plan.errors.length && !plan.lines.length).toBe(true)
  })
  it('patches only the changed field, trimmed', () => {
    const plan = planChanges(CATS, edited([[1, { sub_category: 'Supermarket ' }]]), CATEGORIES)
    expect(plan.updates).toEqual([[1, { sub_category: 'Supermarket' }]])
    expect(plan.lines).toEqual(['Rename Food › Groceries → Food › Supermarket'])
  })
  it('reads a cost type change as a sentence', () => {
    const plan = planChanges(CATS, edited([[2, { cost_type: 'Variable' }]]), CATEGORIES)
    expect(plan.updates).toEqual([[2, { cost_type: 'Variable' }]])
    expect(plan.lines).toEqual(['Leisure › Streaming: cost type → Variable'])
  })
  it('posts a new row', () => {
    const plan = planChanges(CATS, edited([], [], [{ primary_category: 'Pets', sub_category: 'Vet', cost_type: 'Variable' }]), CATEGORIES)
    expect(plan.adds).toEqual([{ primary_category: 'Pets', sub_category: 'Vet', cost_type: 'Variable', for_pets: false }])
    expect(plan.lines).toEqual(['Add Pets › Vet'])
  })
  it('ignores an untouched blank row', () => {
    const plan = planChanges(CATS, edited([], [], [{ primary_category: null, sub_category: '', cost_type: null }]), CATEGORIES)
    expect(isEmptyPlan(plan) && !plan.errors.length).toBe(true)
  })
  it('blocks a half-filled row', () => {
    const plan = planChanges(CATS, edited([], [], [{ primary_category: 'Pets', sub_category: null, cost_type: 'Variable' }]), CATEGORIES)
    expect(plan.adds).toEqual([])
    expect(plan.errors).toEqual(['Fill in every column for “Pets › …”.'])
  })
  it('deletes an unused row and blocks one in use', () => {
    expect(planChanges(CATS, edited([], [2]), CATEGORIES)).toMatchObject({ deletes: [2], lines: ['Remove Leisure › Streaming'] })
    const plan = planChanges(CATS, edited([], [1]), CATEGORIES)
    expect(plan.deletes).toEqual([])
    expect(plan.errors).toEqual([
      "Food › Groceries can't be removed: 3 expenses use it. Rename it instead, or delete those expenses first."])
  })
  it('catches duplicates case-insensitively', () => {
    const plan = planChanges(CATS, edited([], [], [{ primary_category: 'food', sub_category: 'groceries', cost_type: 'Fixed' }]), CATEGORIES)
    expect(plan.errors).toEqual(['food › groceries appears twice.'])
  })
  it('handles payment methods: blank institution stays null, credit is a bool', () => {
    const PMS: Row[] = [{ payment_method_id: 5, method_name: 'Pix', institution: null, is_credit: false, expense_count: 0 }]
    const plan = planChanges(PMS, [{ ...PMS[0], institution: '' },
      { payment_method_id: null, method_name: 'Credit Card', institution: 'Nubank', is_credit: null, expense_count: null }], PAYMENT_METHODS)
    expect(plan.updates).toEqual([])
    expect(plan.adds).toEqual([{ method_name: 'Credit Card', institution: 'Nubank', is_credit: false, is_joint: false }])
    expect(plan.lines).toEqual(['Add Credit Card · Nubank'])
    const credit = planChanges(PMS, [{ ...PMS[0], institution: 'Nubank', is_credit: true }], PAYMENT_METHODS)
    expect(credit.updates).toEqual([[5, { institution: 'Nubank', is_credit: true }]])
    expect(credit.lines).toEqual(['Rename Pix → Pix · Nubank; Pix · Nubank: credit (offers installments)'])
    const joint = planChanges(PMS, [{ ...PMS[0], is_joint: true }], PAYMENT_METHODS)
    expect(joint.lines).toEqual(['Pix: a joint account (nobody owes for it)'])
    expect(planChanges(PMS, [{ ...PMS[0] }], PAYMENT_METHODS).updates).toEqual([])
  })
  it('ticks pets on a category', () => {
    const plan = planChanges(CATS, edited([[2, { for_pets: true }]]), CATEGORIES)
    expect(plan.lines).toEqual(['Leisure › Streaming: asks which pet'])
  })
  it('adds, renames and blocks removing a pet in use', () => {
    const pets: Row[] = [{ pet_id: 1, name: 'Thor', expense_count: 4 }, { pet_id: 2, name: 'Luna', expense_count: 0 }]
    const plan = planChanges(pets, [{ ...pets[1], name: 'Lua' }, { pet_id: null, name: 'Bob', expense_count: null }], PETS)
    expect(plan.updates).toEqual([[2, { name: 'Lua' }]])
    expect(plan.adds).toEqual([{ name: 'Bob' }])
    expect(plan.errors).toEqual(["Thor can't be removed: 4 expenses use it. Rename it instead, or delete those expenses first."])
  })
})

describe('household split', () => {
  it('drops zero shares and converts to fractions', () => {
    expect(householdPayload(new Map([[12, 60], [13, 40], [14, 0]]))).toEqual([
      [{ user_id: 12, share_pct: 0.6 }, { user_id: 13, share_pct: 0.4 }], null])
    expect(householdPayload(new Map([[12, 100]]))).toEqual([[{ user_id: 12, share_pct: 1 }], null])
  })
  it('explains what is wrong', () => {
    expect(householdPayload(new Map([[12, 60], [13, 30]]))[1]).toBe('Shares must add up to 100% (now 90%).')
    expect(householdPayload(new Map([[12, 0]]))[1]).toBe('Give at least one person a share.')
  })
  it('fills in the rest', () => {
    expect([...fillRest(new Map([[1, 50], [2, 20]]), 1)]).toEqual([[1, 50], [2, 50]])
    expect([...fillRest(new Map([[1, 100], [2, 5]]), 1)]).toEqual([[1, 100], [2, 0]])
    expect([...fillRest(new Map([[1, 50], [2, 80], [3, 0]]), 1)]).toEqual([[1, 50], [2, 50], [3, 0]])
    expect([...fillRest(new Map([[1, 50], [2, 30], [3, 20]]), 1)]).toEqual([[1, 50], [2, 30], [3, 20]])
    expect([...fillRest(new Map([[1, 40]]), 1)]).toEqual([[1, 40]])
  })
})

function history(month: string): AnalyticsPayload {
  const [m3, m2, m1] = [3, 2, 1].map((k) => addMonths(month, -k))
  const r = (m: string, p: string, s: string, h: string) => ({ month: m, primary_category: p, sub_category: s,
    household: h, mine: h, household_to_day: h, mine_to_day: h })
  return {
    month, months: Array.from({ length: 12 }, (_, i) => addMonths(month, i - 11)), is_partial: false, as_of_day: 30,
    rows: [
      r(m3, 'Housing', 'Rent', '2000.00'), r(m3, 'Food', 'Groceries', '300.00'),
      r(m2, 'Housing', 'Rent', '2000.00'), r(m2, 'Food', 'Groceries', '600.00'),
      r(m1, 'Housing', 'Rent', '2000.00'), r(m1, 'Food', 'Groceries', '900.00'), r(m1, 'Leisure', 'Cinema', '80.00'),
      r(month, 'Housing', 'Rent', '2000.00'), r(month, 'Food', 'Groceries', '250.00'), r(month, 'Food', 'Restaurants', '120.00'),
    ],
  }
}

describe('monthly targets', () => {
  it('lists each primary category followed by its sub-categories', () => {
    const rows = targetRows(
      [{ primary_category: 'Food', sub_category: 'Groceries' }, { primary_category: 'Food', sub_category: 'Delivery' },
        { primary_category: 'pets', sub_category: 'Vet' }],
      [{ primary_category: 'Food', sub_category: null, amount: '3000.00' },
        { primary_category: 'Food', sub_category: 'Delivery', amount: '300' }])
    expect(rows.map((r) => r.name)).toEqual(['Food', 'Food › Delivery', 'Food › Groceries', 'pets', 'pets › Vet'])
    expect(rows.map((r) => r.target)).toEqual(['3.000,00', '300,00', '', '', ''])
  })
  it('reads Brazilian amounts and blocks bad ones', () => {
    expect(targetsPayload([{ name: 'Food', target: '3.000,00' }, { name: 'Pets', target: '' }, { name: 'Home', target: null }]))
      .toEqual([[{ primary_category: 'Food', sub_category: null, amount: '3000.00' }], []])
    expect(targetsPayload([{ name: 'Pets › Grooming', target: '200' }])[0])
      .toEqual([{ primary_category: 'Pets', sub_category: 'Grooming', amount: '200.00' }])
    const [, problems] = targetsPayload([{ name: 'Food', target: 'abc' }, { name: 'Pets', target: '0' }])
    expect(problems.map((p) => p.split(':')[0])).toEqual(['Food', 'Pets'])
  })
  it('suggests the average of the last full months, rounded up', () => {
    const h = history('2026-09')
    const [suggested, months] = suggestTargets(h)
    expect(months).toEqual(['2026-07', '2026-08', '2026-09'])
    expect(suggested.get('Food')).toBe(65000)
    expect(suggested.get('Housing')).toBe(200000)
    expect([...suggested.keys()].some((k) => k.includes(' › '))).toBe(true)
    const [late, lateMonths] = suggestTargets({ ...h, first_date: '2026-08-26' })
    expect(lateMonths).toEqual(['2026-09'])
    expect(late.get('Food')).toBe(40000)
    expect(suggestTargets(null)).toEqual([new Map(), []])
  })
  it('fills blank whole-category targets only when asked', () => {
    const cats = [{ primary_category: 'Food' }, { primary_category: 'Pets' }]
    const set = [{ primary_category: 'Pets', sub_category: null, amount: '800.00' }]
    const s = new Map([['Food', 65000], ['Pets', 90000]])
    const rows = targetRows(cats, set, s)
    expect(rows.map((r) => r.target)).toEqual(['', '800,00'])
    expect(rows.map((r) => r.suggested)).toEqual(['R$ 650,00', 'R$ 900,00'])
    const filled = targetRows(cats, set, s, true)
    expect(filled.map((r) => r.target)).toEqual(['650,00', '800,00'])
    const subs = targetRows([{ primary_category: 'Pets', sub_category: 'Vet' }], [], new Map([['Pets', 90000], ['Pets › Vet', 40000]]), true)
    expect(subs.map((r) => r.target)).toEqual(['900,00', ''])
    expect(subs.map((r) => r.suggested)).toEqual(['R$ 900,00', 'R$ 400,00'])
  })
})
