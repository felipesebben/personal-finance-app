import { describe, expect, it } from 'vitest'
import { DAY_TO_DAY, EVERYTHING, FIXED, filterRows, isActive, note, NO_FILTERS } from './filtering'
import { label, splitLabel, subs, whole } from './targets'

const rows = [
  { primary_category: 'Food', cost_type: 'Variable', nature: 'Recurring' },
  { primary_category: 'Home', cost_type: 'Fixed', nature: 'Recurring' },
  { primary_category: 'Car', cost_type: 'Variable', nature: 'Annual' },
]

describe('filterRows', () => {
  it('keeps everything without filters', () => {
    expect(filterRows(rows, NO_FILTERS)).toHaveLength(3)
    expect(isActive(NO_FILTERS)).toBe(false)
  })
  it('narrows by what to count, categories and one-offs', () => {
    expect(filterRows(rows, { ...NO_FILTERS, focus: DAY_TO_DAY }).map((r) => r.primary_category)).toEqual(['Food', 'Car'])
    expect(filterRows(rows, { ...NO_FILTERS, focus: FIXED }).map((r) => r.primary_category)).toEqual(['Home'])
    expect(filterRows(rows, { ...NO_FILTERS, categories: ['Car'] })).toHaveLength(1)
    expect(filterRows(rows, { ...NO_FILTERS, withoutOneOffs: true })).toHaveLength(2)
  })
  it('says what is counted', () => {
    expect(note(NO_FILTERS)).toBe('')
    expect(note({ focus: DAY_TO_DAY, categories: ['Food', 'Pets'], withoutOneOffs: true }))
      .toBe('day-to-day costs · Food, Pets · without one-offs')
    expect(note({ focus: EVERYTHING, categories: [], withoutOneOffs: true })).toBe('without one-offs')
  })
})

describe('targets', () => {
  const t = [
    { primary_category: 'Pets', sub_category: null, amount: '500.00' },
    { primary_category: 'Pets', sub_category: 'Grooming', amount: '120.00' },
    { primary_category: 'Food', sub_category: null, amount: '1500' },
  ]
  it('splits whole and sub-category targets', () => {
    expect([...whole(t)]).toEqual([['Pets', 50000], ['Food', 150000]])
    expect([...subs(t, 'Pets')]).toEqual([['Grooming', 12000]])
    expect([...subs(t)]).toEqual([['Pets › Grooming', 12000]])
  })
  it('names them', () => {
    expect(label('Pets', 'Grooming')).toBe('Pets › Grooming')
    expect(splitLabel('Pets › Grooming')).toEqual(['Pets', 'Grooming'])
    expect(splitLabel('Pets')).toEqual(['Pets', null])
  })
})
