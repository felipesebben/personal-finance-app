import { describe, expect, it } from 'vitest'
import { jointLines, mergeForMine, settleLine, spendingLine, type AnalyticsPayload, type AnalyticsRow, type Lens } from './briefing'
import { addMonths } from './dates'

function row(month: string, primary: string, sub: string, costType: string, household: string, mine: string,
  count = 1, householdToDay?: string, mineToDay?: string): AnalyticsRow {
  return {
    month, primary_category: primary, sub_category: sub, cost_type: costType, household, mine, count,
    household_to_day: householdToDay ?? household, mine_to_day: mineToDay ?? mine,
  }
}

function samplePayload(month = '2026-10', isPartial = true, asOfDay = 10): AnalyticsPayload {
  const [m3, m2, m1] = [3, 2, 1].map((k) => addMonths(month, -k))
  return {
    month, months: Array.from({ length: 12 }, (_, i) => addMonths(month, i - 11)), is_partial: isPartial, as_of_day: asOfDay,
    rows: [
      row(m3, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(m3, 'Food', 'Groceries', 'Variable', '300.00', '180.00', 3, '100.00', '60.00'),
      row(m2, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(m2, 'Food', 'Groceries', 'Variable', '600.00', '360.00', 4, '200.00', '120.00'),
      row(m1, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00', 1, '2000.00', '1200.00'),
      row(m1, 'Food', 'Groceries', 'Variable', '900.00', '540.00', 6, '150.00', '90.00'),
      row(m1, 'Leisure', 'Cinema', 'Variable', '80.00', '48.00', 1, '0.00', '0.00'),
      row(month, 'Housing', 'Rent', 'Fixed', '2000.00', '1200.00'),
      row(month, 'Food', 'Groceries', 'Variable', '250.00', '150.00', 3),
      row(month, 'Food', 'Restaurants', 'Variable', '120.00', '72.00', 2),
    ],
  }
}

const line = (p: AnalyticsPayload, label = 'Shared', lens: Lens = 'household', top = false) => spendingLine(label, p, lens, top)

describe('spendingLine', () => {
  it('compares shared spending with the usual same days', () => {
    expect(line(samplePayload(), 'Shared', 'household', true)).toBe(
      'Shared: R$ 2.370,00 so far in October, ▲ R$ 220,00 more than usual by the 10th. Biggest: Housing.')
  })
  it('uses the mine column for my share', () => {
    expect(line(samplePayload(), 'Yours', 'mine')).toBe(
      'Yours: R$ 1.422,00 so far in October, ▲ R$ 132,00 more than usual by the 10th.')
  })
  it('points down when less than usual', () => {
    const p = samplePayload()
    p.rows = p.rows.filter((r) => !(r.month === '2026-10' && r.primary_category === 'Housing'))
    expect(line(p)).toContain('▼ R$ 1.780,00 less than usual by the 10th')
  })
  it('compares with last month without three months', () => {
    const p = samplePayload()
    p.rows = p.rows.filter((r) => ['2026-09', '2026-10'].includes(r.month))
    expect(line(p)).toBe('Shared: R$ 2.370,00 so far in October, ▲ R$ 220,00 more than September by the 10th.')
  })
  it('makes no comparison in the first month', () => {
    const p = samplePayload()
    p.rows = p.rows.filter((r) => r.month === '2026-10')
    expect(line(p)).toBe('Shared: R$ 2.370,00 so far in October.')
  })
  it('says "in" for a finished month', () => {
    const p = samplePayload('2026-10', false, 31)
    expect(line(p)).toMatch(/^Shared: R\$ 2\.370,00 in October, /)
    expect(line(p)).not.toContain('by the')
  })
  it('leaves out nothing at all', () => {
    const p = samplePayload()
    p.rows = []
    expect(line(p)).toBeNull()
  })
  it('adds shared and personal rows for yours', () => {
    const p = samplePayload()
    const shared = { ...p, rows: p.rows.filter((r) => r.month === '2026-10') }
    const personal = { ...p, rows: [row('2026-10', 'Health', 'Pharmacy', 'Variable', '30.00', '30.00')] }
    expect(line(mergeForMine(shared, personal)!, 'Yours', 'mine')).toBe('Yours: R$ 1.452,00 so far in October.')
  })
})

describe('settleLine and jointLines', () => {
  it('says who owes whom from my point of view', () => {
    const owed = { transfers: [{ from_user_id: 2, from_name: 'Lívia', to_user_id: 1, to_name: 'Felipe', amount: '120.00' }] }
    expect(settleLine(owed, 1, 'October')).toBe('Settle up: Lívia owes you R$ 120,00 for October.')
    expect(settleLine(owed, 2, 'October')).toBe('Settle up: You owe Felipe R$ 120,00 for October.')
    expect(settleLine({ transfers: [] }, 1, 'October')).toBe('Settle up: all square for October.')
    expect(settleLine(null, 1, 'October')).toBeNull()
  })
  it('gives a joint line only with a known balance', () => {
    const s = { label: 'Debit · Nubank', balance: '1150.00', runs_out_on: '2026-10-28', month: '2026-10' }
    expect(jointLines([s])).toEqual(['Joint account: R$ 1.150,00 left. At this pace the money lasts until 28 October.'])
    const two = jointLines([s, { ...s, label: 'Pix · Inter', runs_out_on: '2026-11-02' }])
    expect(two[1]).toBe('Joint account (Pix · Inter): R$ 1.150,00 left. At this pace the money lasts past the end of the month.')
    expect(jointLines([{ ...s, balance: null }])).toEqual([])
    expect(jointLines(null)).toEqual([])
  })
})
