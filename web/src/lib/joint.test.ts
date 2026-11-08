import { describe, expect, it } from 'vitest'
import {
  countedFromText, jointAvailable, jointCards, paceGap, paceSentence, paceSeries, runOutText, type JointStatus,
} from './joint'
import { ordinal } from './dates'

function status(over: Partial<JointStatus> = {}): JointStatus {
  return {
    payment_method_id: 15, label: 'Debit · Nubank Conjunta',
    balance: '500.00', counted_from: '2026-12-01T11:00:00Z',
    deposits_since: '0.00', spent_since: '500.00',
    month: '2026-12', as_of_day: 3, days_in_month: 31,
    spent_to_day: '500.00', usual_to_day: '400.00', usual_month_total: '450.00',
    history_months: 2, runs_out_on: '2026-12-20',
    days: [
      { day: 1, this_month: '0', usual: '100.00' },
      { day: 2, this_month: '200.00', usual: '300.00' },
      { day: 3, this_month: '500.00', usual: '400.00' },
      { day: 4, this_month: null, usual: '450.00' },
    ],
    ...over,
  }
}

describe('joint account', () => {
  it('writes ordinals', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 31].map(ordinal))
      .toEqual(['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '31st'])
  })

  it('stops this month at today and keeps the usual line', () => {
    const s = paceSeries(status())
    expect(s.thisMonth.map((p) => p.x)).toEqual([1, 2, 3])
    expect(s.usual.map((p) => p.x)).toEqual([1, 2, 3, 4])
    expect(s.usual.at(-1)!.y).toBe(45000)
  })

  it('has only this month without history', () => {
    const s = paceSeries(status({ days: [{ day: 1, this_month: '10.00', usual: null }] }))
    expect(s.usual).toEqual([])
    expect(s.thisMonth).toHaveLength(1)
  })

  it('uses arrows and says when history is missing', () => {
    expect(paceGap(status())).toBe(10000)
    expect(paceSentence(status())).toBe('By the 3rd you\'ve spent R$ 500,00, ▲ R$ 100,00 more than usual by now (R$ 400,00).')
    expect(paceSentence(status({ spent_to_day: '300.00' }))).toContain('▼ R$ 100,00 less')
    expect(paceSentence(status({ spent_to_day: '400.00' }))).toContain('right on the usual pace')
    const noHistory = status({ usual_to_day: null })
    expect(paceGap(noHistory)).toBeNull()
    expect(paceSentence(noHistory)).toContain('Not enough history yet')
  })

  it('says when the money runs out', () => {
    expect(runOutText(status())).toBe('At this pace the money lasts until 20 December.')
    expect(runOutText(status({ runs_out_on: '2027-01-04' }))).toBe('At this pace the money lasts past the end of the month.')
    expect(runOutText(status({ balance: '0.00', runs_out_on: '2026-12-03' }))).toBe('The account is empty.')
    expect(runOutText(status({ runs_out_on: null }))).toContain('Nothing spent yet')
    expect(runOutText(status({ balance: null }))).toBeNull()
  })

  it('says what the balance counts from', () => {
    expect(countedFromText(status())).toMatch(/^From the balance you entered on 01\/12\/2026/)
    expect(countedFromText(status({ counted_from: null }))).toMatch(/^From your first deposit/)
    expect(countedFromText(status({ balance: null }))).toBe('Enter the balance your bank shows to start.')
  })

  it('builds the three cards', () => {
    const [left, spent, runs] = jointCards(status())
    expect(left[1]).toBe('R$ 500,00')
    expect(spent[2][0]).toEqual(['▲ R$ 100 vs usual', 'more'])
    expect(runs[1]).toBe('20/12')
  })

  it('is available to household members once a method is joint', () => {
    const household = [{ user_id: 1, share_pct: '0.6', user: { user_id: 1, full_name: 'A', email: 'a@x' } }]
    expect(jointAvailable([{ is_joint: true }], household, 1)).toBe(true)
    expect(jointAvailable([{ is_joint: true }], household, 2)).toBe(false)
    expect(jointAvailable([{ is_joint: false }], household, 1)).toBe(false)
  })
})
