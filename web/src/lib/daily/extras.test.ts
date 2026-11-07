import { describe, expect, it } from 'vitest'
import { dayTitle, EMPTY_DAY, HEAT, isDark, shade } from './calendar'
import { notices } from './notices'
import { installmentsDue, recurringDue, type Expense } from './upcoming'
import { change, whereBars } from './where'
import type { CalDay } from './shaping'

describe('calendar', () => {
  it('shades from the lightest green to brand green', () => {
    expect(shade(0, 100)).toBe(EMPTY_DAY)
    expect(shade(1e-9, 100)).toBe(HEAT[0])
    expect(shade(100, 100)).toBe(HEAT[1])
    expect(shade(5000, 100)).toBe(HEAT[1])
    expect(isDark(300, 200)).toBe(true)
    expect(isDark(10, 200)).toBe(false)
  })

  it('says what a day held, and only the date for days to come', () => {
    const day: CalDay = { date: '2026-10-23', day: 23, week: 3, weekday: 4, amount: 30000, count: 1,
      top_category: 'Food', state: 'past', label: 'Friday 23 October' }
    expect(dayTitle(day)).toBe('Friday 23 October · R$ 300,00 · 1 expense · mostly Food')
    expect(dayTitle({ ...day, state: 'future' })).toBe('Friday 23 October')
  })
})

describe('notices', () => {
  it('puts what is over first, then near, then late bills', () => {
    const due = [{ name: 'Health › Boxing', amount: 80000, day: 9 }, { name: 'Housing › Internet', amount: 9990, day: 25 }]
    const lines = notices(new Map([['Food', 350000], ['Pets', 100000], ['Home', 50000]]),
      new Map([['Food', 390000], ['Pets', 95000], ['Home', 10000]]), due, 23, 31)
    expect(lines).toEqual([
      ['Food is past its monthly target: R$ 3.900,00 of R$ 3.500,00.', 'more'],
      ['Pets is at 95% of its monthly target with 8 days to go.', null],
      ["Boxing (R$ 800,00) usually comes by the 9th and isn't logged yet.", null],
    ])
    expect(notices(new Map(), new Map(), [], 5, 31)).toEqual([])
  })
})

const POWER = { primary_category: 'Housing', sub_category: 'Electricity', cost_type: 'Fixed' }
const NET = { primary_category: 'Housing', sub_category: 'Internet', cost_type: 'Fixed' }
const SOFA = { primary_category: 'Home', sub_category: 'Furniture', cost_type: 'Variable' }

function expense(id: number, when: string, price: string, extra: Partial<Expense> = {}): Expense {
  return { expenditure_id: id, transaction_timestamp: when, price, nature: 'Normal', is_shared: true, my_share: '60.00',
    total_installments: 1, current_installment: 1, category: POWER, ...extra }
}
const bill = (id: number, when: string, price: string, category = POWER, extra: Partial<Expense> = {}) =>
  expense(id, when, price, { category, nature: 'Recurring', my_share: price, ...extra })

describe('still to come', () => {
  it('lists a recurring bill not logged yet at its latest amount and day', () => {
    const due = recurringDue([
      bill(1, '2026-08-10T15:00:00+00:00', '150.00'),
      bill(2, '2026-09-12T15:00:00+00:00', '180.00'),
      bill(3, '2026-09-05T15:00:00+00:00', '99.90', NET),
      bill(4, '2026-10-04T15:00:00+00:00', '99.90', NET),
      bill(5, '2026-05-01T15:00:00+00:00', '70.00', SOFA),
    ], '2026-10', 'all', 'Household')
    expect(due.map((d) => [d.name, d.amount, d.text, d.cost_type, d.nature])).toEqual([
      ['Housing › Electricity', 18000, 'R$ 180 · usually the 12th', 'Fixed', 'Recurring']])
  })

  it('lists installments billed this month until paid off', () => {
    const sofa = expense(1, '2026-07-20T15:00:00+00:00', '1000.03',
      { category: SOFA, total_installments: 4, current_installment: 1, my_share: '600.02' })
    const due = installmentsDue([sofa], '2026-10', 'all', 'Household')
    expect(due.map((d) => [d.text, d.amount, d.name])).toEqual([['R$ 250 · 4 of 4', 25003, 'Home › Furniture · 20/07']])
    expect(installmentsDue([sofa], '2026-08', 'all', 'Household').map((d) => d.amount)).toEqual([25000])
    expect(installmentsDue([sofa], '2026-11', 'all', 'Household')).toEqual([])
    expect(installmentsDue([sofa], '2026-07', 'all', 'Household')).toEqual([])
    expect(installmentsDue([{ ...sofa, current_installment: 3 }], '2026-09', 'all', 'Household')).toEqual([])
    expect(installmentsDue([sofa], '2026-10', 'all', 'My share').map((d) => d.amount)).toEqual([15002])
  })

  it('follows the view and the lens', () => {
    const both = [bill(1, '2026-09-12T15:00:00+00:00', '180.00', POWER, { my_share: '108.00' }),
      bill(2, '2026-09-03T15:00:00+00:00', '50.00', NET, { is_shared: false })]
    expect(recurringDue(both, '2026-10', 'shared', 'Household').map((d) => d.name)).toEqual(['Housing › Electricity'])
    expect(recurringDue(both, '2026-10', 'personal', 'My share').map((d) => d.name)).toEqual(['Housing › Internet'])
    expect(Object.fromEntries(recurringDue(both, '2026-10', 'all', 'My share').map((d) => [d.name, d.amount])))
      .toEqual({ 'Housing › Electricity': 10800, 'Housing › Internet': 5000 })
    expect(recurringDue([], '2026-10', 'all', 'Household')).toEqual([])
  })
})

describe('where', () => {
  it('measures a change in reais or against what it was', () => {
    expect(change({ name: 'Food', amount: 8000, previous: 15000 }, 'R$')).toEqual({ value: -7000, text: '▼ R$ 70' })
    expect(change({ name: 'Food', amount: 8000, previous: 15000 }, '%')).toEqual({ value: -7000 / 15000, text: '▼ 47%' })
    expect(change({ name: 'Pets', amount: 22000, previous: 0 }, '%')).toEqual({ value: null, text: 'new' })
  })

  it('puts the change at the tip on a narrow screen and the share without a comparison', () => {
    const items = [{ name: 'Pets', amount: 22000, previous: 0, target: 30000 }, { name: 'Food', amount: 8000, previous: 15000 }]
    const wide = whereBars(items, 'R$', 'Pets', false)
    expect(wide.bars.map((b) => b.text)).toEqual(['R$ 220', 'R$ 80'])
    expect(wide.bars.map((b) => [b.tick, b.target, b.picked])).toEqual([[null, 30000, true], [15000, null, false]])
    expect(wide.changes!.map((c) => c.text)).toEqual(['▲ R$ 220', '▼ R$ 70'])
    const narrow = whereBars(items, '%', null, true)
    expect(narrow.changes).toBeNull()
    expect(narrow.bars.map((b) => b.text)).toEqual(['R$ 220 · new', 'R$ 80 · ▼ 47%'])
    const plain = whereBars([{ name: 'Pets', amount: 22000 }, { name: 'Food', amount: 8000 }], 'R$', null, false)
    expect(plain.changes).toBeNull()
    expect(plain.bars.map((b) => b.text)).toEqual(['R$ 220 · 73%', 'R$ 80 · 27%'])
  })
})
