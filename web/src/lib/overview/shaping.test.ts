import { describe, expect, it } from 'vitest'
import { emptyPayload, row, samplePayload } from './fixtures'
import {
  biggestChanges, biggestIncrease, changePct, compare, compareTotal, deltaLine, deltaText, expenseCount,
  mergePayloads, monthLabel, monthOptions, monthlyCounts, monthlyTotals, ordinal, partlyLoggedFrom,
  previousFullAverage, shiftMonth, toRows, trackedSince,
} from './shaping'

const df = toRows(samplePayload())
const months = samplePayload().months
const byKey = <T extends { key: string }>(xs: T[]) => Object.fromEntries(xs.map((x) => [x.key, x]))

describe('months', () => {
  it('shifts across years', () => {
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2025-12', 1)).toBe('2026-01')
    expect(shiftMonth('2026-10', -12)).toBe('2025-10')
  })
  it('lists options newest first and labels them', () => {
    expect(monthOptions('2026-02', 4)).toEqual(['2026-02', '2026-01', '2025-12', '2025-11'])
    expect(monthLabel('2026-10')).toBe('Oct 2026')
    expect(monthLabel('2026-01', true)).toBe('Jan 26')
  })
})

describe('rows and totals', () => {
  it('parses amounts into cents', () => {
    expect(df.reduce((s, r) => s + r.household, 0)).toBe(1025000)
    expect(toRows(emptyPayload())).toEqual([])
    expect(toRows(null)).toEqual([])
  })
  it('zero-fills totals in window order', () => {
    const totals = monthlyTotals(df, months, 'Household')
    expect([...totals.keys()]).toEqual(months)
    expect(totals.get('2025-11')).toBe(0)
    expect(totals.get('2026-09')).toBe(298000)
    expect(totals.get('2026-10')).toBe(237000)
    expect(monthlyTotals(df, months, 'My share').get('2026-10')).toBe(142200)
    expect(monthlyTotals(df, months, 'Household', true).get('2026-09')).toBe(215000)
    expect([...monthlyTotals([], months, 'Household').values()].every((v) => v === 0)).toBe(true)
  })
  it('counts expenses', () => {
    expect(expenseCount(df, '2026-10')).toBe(6)
    expect(expenseCount(df, '2026-01')).toBe(0)
    expect([...monthlyCounts(df, months).keys()]).toEqual(months)
  })
})

describe('comparisons', () => {
  it('compares a partial month with the same days of the previous one', () => {
    const comp = compare(df, '2026-10', true, 'Household')
    expect(comp.map((c) => c.key)).toEqual(['Housing', 'Food'])
    const food = byKey(comp).Food
    expect([food.current, food.previous, food.change]).toEqual([37000, 15000, 22000])
    expect(food.pct).toBeCloseTo(220 / 150)
    expect(comp.some((c) => c.key === 'Leisure')).toBe(false)
  })
  it('compares a complete month with the whole previous month', () => {
    const comp = byKey(compare(df, '2026-10', false, 'Household'))
    expect(comp.Food.previous).toBe(90000)
    expect(comp.Leisure.current).toBe(0)
    expect(comp.Leisure.pct).toBe(-1)
  })
  it('has no pct for a new category', () => {
    const payload = samplePayload()
    payload.rows.push(row('2026-10', 'Travel', 'Flights', 'Variable', '500.00', '300.00'))
    const comp = compare(toRows(payload), '2026-10', true, 'Household')
    expect(byKey(comp).Travel.pct).toBeNull()
    expect(biggestIncrease(comp)).toBe('Travel')
  })
  it('compares sub-categories inside one category', () => {
    const sub = compare(df, '2026-10', true, 'My share', 'sub_category', { primary_category: 'Food' })
    expect(sub.map((s) => s.key)).toEqual(['Groceries', 'Restaurants'])
    expect(sub.map((s) => s.current)).toEqual([15000, 7200])
    expect(sub.map((s) => s.previous)).toEqual([9000, 0])
  })
  it('compares the total', () => {
    const total = compareTotal(df, '2026-10', true, 'Household')
    expect([total.current, total.previous, total.change]).toEqual([237000, 215000, 22000])
    expect(total.pct).toBeCloseTo(220 / 2150)
    const empty = compareTotal([], '2026-10', true, 'Household')
    expect(empty.current).toBe(0)
    expect(empty.pct).toBeNull()
  })
  it('averages the three previous full months', () => {
    expect(previousFullAverage(df, months, '2026-10', 'Household')).toBe(262667)
    expect(previousFullAverage(df, months, '2026-10', 'Household', 3, true)).toBe(215000)
    expect(previousFullAverage(df, months, '2026-09', 'Household')).toBeNull()
    expect(previousFullAverage(df, months.slice(-3), '2026-10', 'Household')).toBeNull()
    expect(previousFullAverage([], months, '2026-10', 'Household')).toBeNull()
    expect(previousFullAverage(df, months, '2026-10', 'Household', 3, false, '2026-08')).toBeNull()
  })
  it('finds the biggest increase and changes', () => {
    const rising = compare(df, '2026-10', true, 'Household')
    expect(biggestIncrease(rising)).toBe('Food')
    expect(biggestChanges(rising).map((c) => c.key)).toEqual(['Food'])
    const falling = compare(df, '2026-10', false, 'Household')
    expect(biggestIncrease(falling)).toBeNull()
    expect(biggestChanges(falling).map((c) => c.key)).toEqual(['Food', 'Leisure'])
    expect(biggestIncrease([])).toBeNull()
  })
})

describe('text', () => {
  it('writes changes', () => {
    expect(changePct(0.125)).toBe('+12,5%')
    expect(changePct(-0.5)).toBe('-50,0%')
    expect(changePct(null)).toBe('new')
    expect(deltaText(22000, 220 / 150)).toBe('+R$ 220,00 (+146,7%)')
    expect(deltaText(5000, null)).toBe('+R$ 50,00 (new)')
    expect(deltaLine(0, null, 'Sep')).toEqual(['Same as Sep', null])
    expect(deltaLine(-1000, -0.1, 'Sep')).toEqual(['▼ R$ 10 (10%) vs Sep', 'less'])
  })
})

describe('months logged in full', () => {
  it('starts comparisons at the first whole month', () => {
    expect(trackedSince('2026-09-26')).toBe('2026-10')
    expect(trackedSince('2026-09-05')).toBe('2026-09')
    expect(trackedSince(null)).toBeNull()
    expect(partlyLoggedFrom('2026-09', '2026-09-26')).toBe(26)
    expect(partlyLoggedFrom('2026-09', '2026-09-05')).toBeNull()
    expect(partlyLoggedFrom('2026-08', '2026-09-26')).toBeNull()
    expect([1, 2, 3, 11, 22, 26].map(ordinal)).toEqual(['1st', '2nd', '3rd', '11th', '22nd', '26th'])
  })
  it('merges payloads from the earliest first date', () => {
    const a = { ...emptyPayload(), first_date: '2026-09-26' }
    const b = { ...emptyPayload(), first_date: '2026-08-02', rows: [row('2026-10', 'Food', 'x', 'Variable', '1', '1')] }
    const merged = mergePayloads({ shared: a, personal: b })
    expect(merged.first_date).toBe('2026-08-02')
    expect(merged.rows[0].source).toBe('personal')
    expect(mergePayloads({ shared: emptyPayload() }).first_date).toBeNull()
  })
})
