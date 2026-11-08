import { describe, expect, it } from 'vitest'
import { delta } from './delta'

describe('delta', () => {
  it('fits on one line: arrow, short amount, percentage, what it is against', () => {
    expect(delta(181082, 462084, 'October')).toEqual(['▲ R$ 1,8 mil (39%) vs October', 'more'])
    expect(delta(-43305, 324307, 'usual')).toEqual(['▼ R$ 433 (13%) vs usual', 'less'])
  })
  it('leaves out the percentage without an earlier amount, and says "same" under 50 cents', () => {
    expect(delta(10000, null, 'usual')).toEqual(['▲ R$ 100 vs usual', 'more'])
    expect(delta(10000, 0, 'usual')).toEqual(['▲ R$ 100 vs usual', 'more'])
    expect(delta(30, 1000, 'Sep')).toEqual(['Same as Sep', null])
  })
})
