import { describe, expect, it } from 'vitest'
import { actionLabels, netText, periodLabel, personLines } from './settle'

const t = { from_user_id: 2, from_name: 'Lívia', to_user_id: 1, to_name: 'Felipe', amount: '447.53' }

describe('settle up', () => {
  it('speaks in the viewer\'s voice', () => {
    expect(actionLabels(t, 2)).toEqual({ all: 'I paid Felipe R$ 447,53', other: 'I paid Felipe a different amount' })
    expect(actionLabels(t, 1)).toEqual({ all: 'Lívia paid me R$ 447,53', other: 'Lívia paid me a different amount' })
    expect(actionLabels(t, 9).all).toBe('Lívia paid Felipe R$ 447,53')
  })
  it('says where each person stands', () => {
    expect(netText('120.00')).toBe('Is owed R$ 120,00')
    expect(netText('-120.00')).toBe('Owes R$ 120,00')
    expect(netText('0.00')).toBe('Square')
    expect(personLines({ user_id: 1, full_name: 'A', paid: '10', borne: '6', settled_out: '0', settled_in: '2', net: '2' }))
      .toEqual([['Paid R$ 10,00', null], ['Their share R$ 6,00', null], ['Received R$ 2,00', null]])
  })
  it('names a period', () => {
    expect(periodLabel('2026-10')).toBe('October 2026')
    expect(periodLabel('All time')).toBe('All time')
  })
})
