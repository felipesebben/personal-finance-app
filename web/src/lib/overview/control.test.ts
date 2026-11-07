import { describe, expect, it } from 'vitest'
import {
  controlLines, controlRows, controllable, fixedCosts, oneOffs, reserve, reserveLines, toRows, usualBefore,
  type ApiRow,
} from './shaping'

const MONTHS = ['2026-07', '2026-08', '2026-09', '2026-10', '2026-11']

function r(month: string, category: string, amount: number, costType = 'Variable', nature = 'Normal',
  toDay?: number, sub = 'x'): ApiRow {
  const a = String(amount)
  const t = String(toDay ?? amount)
  return { month, primary_category: category, sub_category: sub, cost_type: costType, nature,
    household: a, mine: a, household_to_day: t, mine_to_day: t, count: 1 }
}
const rows = (xs: ApiRow[]) => toRows({ month: '', months: [], is_partial: false, as_of_day: 1, rows: xs })

describe('what we control', () => {
  it('is variable without one-offs', () => {
    const df = rows([r('2026-10', 'Food', 100), r('2026-10', 'Housing', 900, 'Fixed'), r('2026-10', 'Housing', 120),
      r('2026-10', 'Transport', 3000, 'Variable', 'Extraordinary')])
    expect(controllable(df).map((x) => x.household).sort()).toEqual([10000, 12000])
    expect(fixedCosts(df).map((x) => x.household)).toEqual([90000])
    expect(oneOffs(df).map((x) => x.household)).toEqual([300000])
  })

  it('takes the usual month as the average of up to three full months', () => {
    const totals = new Map(MONTHS.map((m, i) => [m, [5000, 10000, 20000, 30000, 99900][i]]))
    expect(usualBefore(totals, '2026-11', '2026-07')).toBe(20000)
    expect(usualBefore(totals, '2026-11', '2026-10')).toBe(30000)
    expect(usualBefore(totals, '2026-10', '2026-10')).toBeNull()
  })

  it('flags a category above usual two months running', () => {
    const xs = [
      ...MONTHS.map((m, i) => r(m, 'Food', [100, 100, 100, 150, 200][i])),
      ...MONTHS.map((m, i) => r(m, 'Pets', [300, 300, 300, 300, 290][i])),
      r('2026-11', 'Housing', 5000, 'Fixed'),
    ]
    const out = controlRows(rows(xs), MONTHS, '2026-11', 'Household', false, '2026-07')
    expect(out.map((x) => x.name)).toEqual(['Pets', 'Food'])
    expect(out[1].usual).toBe(Math.round((10000 + 10000 + 15000) / 3))
    expect(out[1].streak).toBe(2)
    expect(out[0].streak).toBe(0)
    const lines = controlLines(out)
    expect(lines[0]).toEqual(['Above usual for two months or more: Food.', 'more'])
    expect(lines[1][0].startsWith('Where you could save: Food R$ 83,33 above usual')).toBe(true)
  })

  it('compares a month in progress over the same days', () => {
    const [food] = controlRows(rows([r('2026-10', 'Food', 300, 'Variable', 'Normal', 100), r('2026-11', 'Food', 105)]),
      MONTHS, '2026-11', 'Household', true, '2026-10')
    expect(food.usual).toBe(10000)
    expect(food.change).toBe(500)
    expect(food.streak).toBe(0)
    expect(controlLines([food])).toEqual([['Everything you control is within 10% of usual.', 'less']])
  })

  it('has no usual before a whole month', () => {
    const [food] = controlRows(rows([r('2026-11', 'Food', 105)]), MONTHS, '2026-11', 'Household', true, '2026-11')
    expect(food.usual).toBeNull()
    expect(food.pct).toBeNull()
    expect(controlLines([food])[0][0].startsWith('The usual month appears')).toBe(true)
  })
})

describe('the reserve', () => {
  it('averages one-offs over full months and names the annual bills', () => {
    const df = rows([
      r('2026-08', 'Transport', 1200, 'Variable', 'Annual', undefined, 'IPVA'),
      r('2026-08', 'Food', 500, 'Variable', 'Normal', undefined, 'Groceries'),
      r('2026-09', 'Pets', 610, 'Variable', 'Extraordinary', undefined, 'Vet'),
      r('2026-10', 'Food', 400, 'Variable', 'Normal', undefined, 'Groceries'),
      r('2026-11', 'Health', 9999, 'Variable', 'Extraordinary', undefined, 'Surgery'),
    ])
    const res = reserve(df, MONTHS, '2026-11', 'Household', '2026-08')!
    expect(res.months).toBe(3)
    expect(res.rough).toBe(true)
    expect(res.monthly).toBe(65000)
    expect(res.coming).toEqual([['IPVA', '2027-08', 120000]])
    const lines = reserveLines(res).map(([t]) => t)
    expect(lines[0]).toBe('Set aside about R$ 650,00 a month for them (a rough guess from 3 months logged)')
    expect(lines[1]).toBe('Coming round: IPVA in Aug 27, R$ 1.200,00 last time')
  })

  it('waits for a whole month', () => {
    const df = rows([r('2026-11', 'Health', 100, 'Variable', 'Extraordinary')])
    expect(reserve(df, MONTHS, '2026-11', 'Household', '2026-11')).toBeNull()
    expect(reserveLines(null)[0][0].startsWith('A reserve to set aside appears')).toBe(true)
  })
})
