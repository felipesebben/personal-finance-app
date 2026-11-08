import { describe, expect, it } from 'vitest'
import { barPath } from './palette'

describe('barPath', () => {
  it('is square at the axis and rounded only at the far end', () => {
    // A bar from x=10 growing right: starts with a straight edge at x=10, arcs only at x=110.
    expect(barPath(10, 0, 100, 20, 6, 'right')).toBe('M10,0H104A6,6 0 0 1 110,6V14A6,6 0 0 1 104,20H10Z')
    // Growing left from x=110: the straight edge stays at 110.
    expect(barPath(10, 0, 100, 20, 6, 'left')).toBe('M110,0H16A6,6 0 0 0 10,6V14A6,6 0 0 0 16,20H110Z')
    // A column on a baseline at y=50: flat bottom, round top.
    expect(barPath(0, 10, 20, 40, 6, 'top')).toBe('M0,50V16A6,6 0 0 1 6,10H14A6,6 0 0 1 20,16V50Z')
  })
  it('keeps the radius within the bar and draws nothing for an empty one', () => {
    expect(barPath(0, 0, 3, 20, 6, 'right')).toBe('M0,0H0A3,3 0 0 1 3,3V17A3,3 0 0 1 0,20H0Z')
    expect(barPath(0, 0, 0, 20, 6, 'right')).toBe('')
    expect(barPath(0, 0, 10, 0, 6, 'top')).toBe('')
  })
})
