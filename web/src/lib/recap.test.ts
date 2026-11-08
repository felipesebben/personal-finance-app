import { describe, expect, it } from 'vitest'
import { samplePayload } from './overview/fixtures'
import { toRows } from './overview/shaping'
import { monthRecap } from './recap'

function recapOf(firstDate: string | null = null, targets?: Map<string, number>) {
  const p = samplePayload('2026-10')
  return monthRecap(toRows(p), p.months, p.month, p.is_partial, firstDate, targets)
}

describe('monthRecap', () => {
  it('compares a month with last month and the usual one, and says why', () => {
    const r = recapOf(null, new Map([['Food', 30000], ['Housing', 250000]]))
    expect([r.label, r.total]).toEqual(['Oct 2026 so far', 'R$ 2.370,00'])
    expect(r.lines).toEqual([
      ['▲ R$ 220,00 (10%) more than September by the same day', 'more'],
      ['▲ R$ 220,00 (10%) more than the usual month by the same day', 'more'],
    ])
    expect(r.causes).toEqual([['Day-to-day: ▲ R$ 220,00, now R$ 370,00', 'more']])
    expect(r.moves).toEqual([['Food ▲ R$ 220,00 (147%)', 'more']])
    expect(r.targets).toEqual([
      ['Food: R$ 370,00 of R$ 300,00, ▲ R$ 70,00 over', 'more'],
      ['Housing: R$ 2.000,00 of R$ 2.500,00 (80%)', null],
    ])
  })

  it('names a partly logged last month instead of comparing', () => {
    const r = recapOf('2026-09-26')
    expect(r.lines).toEqual([['September was logged from the 26th only, so not compared yet.', null]])
    expect(r.causes).toEqual([])
    expect(r.moves).toEqual([])
  })

  it('has no target lines without targets', () => {
    expect(recapOf().targets).toEqual([])
  })
})
