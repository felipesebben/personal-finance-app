import { describe, expect, it } from 'vitest'
import {
  cents, entryPreview, formatBrl, installmentAmounts, parseBrl, pctText, shortBrl, signedBrl, splitLikeBackend, toApi,
} from './money'

describe('parseBrl', () => {
  it.each([
    ['45', 4500], ['45,9', 4590], ['45,90', 4590], ['1.234,56', 123456], ['1234,56', 123456],
    ['1234.56', 123456], ['12.5', 1250], ['1.234', 123400], ['1.234.567,89', 123456789],
    ['0,5', 50], [',50', 50], ['R$ 12,50', 1250], ['r$12,50', 1250], ['  1 234,00 ', 123400],
    ['99999999,99', 9999999999],
  ])('reads %s', (typed, expected) => {
    expect(parseBrl(typed)).toBe(expected)
  })

  it.each([
    '', '   ', 'R$', '0', '0,00', '-5', 'abc', '1e3', '12,345', '1,234,56',
    '1.23.4', '12.34.56,00', '1.2345', '100000000', '45,9a',
  ])('rejects %j', (typed) => {
    expect(() => parseBrl(typed)).toThrow()
  })

  it('explains what went wrong', () => {
    expect(() => parseBrl('1.23.4')).toThrow(/comma for cents/)
  })

  it.each([1, 4590, 123456, 9999999999])('round-trips %d', (c) => {
    expect(parseBrl(formatBrl(c))).toBe(c)
  })
})

describe('formatBrl', () => {
  it.each([
    [123450, 'R$ 1.234,50'], [10, 'R$ 0,10'], [123456789, 'R$ 1.234.567,89'], [0, 'R$ 0,00'], [-1200, '-R$ 12,00'],
  ])('formats %d', (c, expected) => {
    expect(formatBrl(c)).toBe(expected)
  })

  it('can leave out the symbol', () => {
    expect(formatBrl(250000, false)).toBe('2.500,00')
  })

  it('signs a change', () => {
    expect(signedBrl(1200)).toBe('+R$ 12,00')
    expect(signedBrl(-350)).toBe('-R$ 3,50')
    expect(signedBrl(0)).toBe('R$ 0,00')
  })

  it('shortens for chart labels', () => {
    expect(shortBrl(82000)).toBe('R$ 820')
    expect(shortBrl(410000)).toBe('R$ 4,1 mil')
    expect(shortBrl(400000)).toBe('R$ 4 mil')
    expect(shortBrl(120000000)).toBe('R$ 1,2 mi')
  })

  it('writes a share', () => {
    expect(pctText(0.6)).toBe('60%')
    expect(pctText(0.625)).toBe('62,5%')
  })
})

describe('API amounts', () => {
  it('reads decimal strings and numbers', () => {
    expect(cents('1234.5')).toBe(123450)
    expect(cents('0.10')).toBe(10)
    expect(cents(12.34)).toBe(1234)
    expect(cents(null)).toBe(0)
  })
  it('writes decimal strings', () => {
    expect(toApi(123456)).toBe('1234.56')
    expect(toApi(5)).toBe('0.05')
    expect(toApi(-1200)).toBe('-12.00')
  })
})

describe('installmentAmounts', () => {
  it.each([
    [120000, 10, 12000, 12000], [4000, 3, 1333, 1334], [10000, 3, 3333, 3334], [5, 3, 1, 3], [4590, 1, 4590, 4590],
  ])('%d in %d parts', (total, count, first, last) => {
    expect(installmentAmounts(total, count)).toEqual([first, last])
    expect(first * (count - 1) + last).toBe(total)
  })
})

describe('splitLikeBackend', () => {
  it('lets the last member absorb the remainder', () => {
    expect([...splitLikeBackend(10001, [[1, 0.6], [2, 0.4]])]).toEqual([[1, 6001], [2, 4000]])
    expect([...splitLikeBackend(10001, [[2, 0.4], [1, 0.6]])]).toEqual([[1, 6001], [2, 4000]])
    expect([...splitLikeBackend(1, [[1, 0.5], [2, 0.5]])]).toEqual([[1, 1], [2, 0]])
  })
  it('drops zero shares', () => {
    expect([...splitLikeBackend(5000, [[1, 0], [2, 1]])]).toEqual([[2, 5000]])
  })
})

describe('entryPreview', () => {
  it.each<[Parameters<typeof entryPreview>, string]>([
    [[120000, 10, [[1, 0.6], [2, 0.4]], 1], 'R$ 1.200,00 · 10x R$ 120,00 · your share 60% = R$ 720,00'],
    [[4590], 'R$ 45,90'],
    [[4000, 3], 'R$ 40,00 · 3x R$ 13,33 (last R$ 13,34)'],
    [[10001, 1, [[1, 0.6], [2, 0.4]], 2], 'R$ 100,01 · your share 40% = R$ 40,00'],
    [[10000, 1, [[1, 0.3333], [2, 0.6667]], 1], 'R$ 100,00 · your share 33,33% = R$ 33,33'],
    [[8000, 1, [[1, 0], [2, 1]], 1], 'R$ 80,00 · your share 0% = R$ 0,00'],
    [[8000, 1, [[1, 0.5], [2, 0.5]], null], 'R$ 80,00'],
    [[8000, 1, [[1, 0.5], [2, 0.5]], 9], 'R$ 80,00'],
  ])('%j', (args, expected) => {
    expect(entryPreview(...args)).toBe(expected)
  })
})
