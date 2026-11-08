import { describe, expect, it } from 'vitest'
import { addMonths } from '../dates'
import { filterRows, NO_FILTERS } from '../filtering'
import {
  againstLastMonth, baselineMonths, biggestDays, byDay, calendarDays, calendarScaleMax, cards, dailyAmounts, dayItems,
  headline, history, loggingStarted, monthReferences, monthsFrame, pace, partlyLoggedFrom, ranked, readRows,
  targetTotal, trackedSince, trackSeries, type ApiDailyRow, type DailyPayload,
} from './shaping'

const MONTHS = ['2026-07', '2026-08', '2026-09', '2026-10']

export function row(date: string, household: string, category = 'Food', sub = 'Groceries', costType = 'Variable',
  nature = 'Normal', count = 1, mine?: string): ApiDailyRow {
  return { date, primary_category: category, sub_category: sub, cost_type: costType, nature, household,
    mine: mine ?? (Number(household) * 0.6).toFixed(2), count }
}

export function payload(rows: ApiDailyRow[], { month = '2026-10', isPartial = true, asOfDay = 10, months = MONTHS } = {}):
  DailyPayload {
  return { month, months: [...months], is_partial: isPartial, as_of_day: asOfDay,
    today: `${month}-${String(asOfDay).padStart(2, '0')}`, rows }
}

const SAMPLE = payload([
  row('2026-07-02', '100.00'),
  row('2026-08-05', '200.00', 'Food', 'Groceries', 'Variable', 'Normal', 2),
  row('2026-08-20', '300.00', 'Home', 'Furniture'),
  row('2026-09-03', '150.00'),
  row('2026-09-15', '450.00', 'Housing', 'Rent', 'Fixed', 'Normal', 3),
  row('2026-10-01', '80.00'),
  row('2026-10-04', '220.00', 'Pets', 'Vet', 'Variable', 'Normal', 2),
])

const frame = (p = SAMPLE) => byDay(readRows(p))

describe('rows and days', () => {
  it('zero-fills daily amounts', () => {
    const oct = dailyAmounts(frame(), '2026-10', 'Household')
    expect(oct).toHaveLength(31)
    expect([oct[0], oct[1], oct[3]]).toEqual([8000, 0, 22000])
    expect(dailyAmounts(frame(), '2026-10', 'My share')[3]).toBe(13200)
  })

  it('sums a day and names its top category', () => {
    const p = payload([row('2026-10-03', '40.00'), row('2026-10-03', '30.00', 'Food', 'Delivery'),
      row('2026-10-03', '60.00', 'Home', 'Furniture')])
    const [day] = byDay(readRows(p))
    expect([day.household, day.count, day.top_category]).toEqual([13000, 3, 'Food'])
  })
})

describe('pace, headline and cards', () => {
  it('compares the same days', () => {
    const p = pace(frame(), SAMPLE, 'Household')
    expect([p.so_far, p.last_by_day, p.usual_by_day]).toEqual([30000, 15000, 15000])
    expect([p.last_total, p.usual_total]).toEqual([60000, 40000])
    expect([p.per_day, p.last_per_day, p.usual_per_day]).toEqual([3000, 1500, 1500])
    expect(p.usual_of).toEqual(['2026-07', '2026-08', '2026-09'])
    expect(p.heading_for).toBe(55000)
    expect([p.reference_name, p.days_left, p.allowance]).toEqual(['usual', 21, Math.round(10000 / 21)])
  })

  it('starts tracking with the unfiltered data', () => {
    const pets = byDay(filterRows(readRows(SAMPLE), { ...NO_FILTERS, categories: ['Pets'] }))
    const p = pace(pets, SAMPLE, 'Household', '2026-07')
    expect([p.has_last, p.last_total, p.usual_total]).toEqual([true, 0, 0])
    expect(pace(pets, SAMPLE, 'Household').has_last).toBe(false)
  })

  it('leads with the answer', () => {
    const h = headline(pace(frame(), SAMPLE, 'Household'))
    expect([h.label, h.amount]).toEqual(['Spent so far in October', 'R$ 300,00'])
    expect(h.lines).toEqual([
      ['▲ R$ 150,00 (100%) more than September by the 10th', 'more'],
      ['▲ R$ 150,00 (100%) more than usual by the 10th', 'more'],
      ['Heading for about R$ 550,00 if the rest of October goes as usual', null],
    ])
    expect(headline(pace(frame(), SAMPLE, 'Household'), 'day-to-day costs').label)
      .toBe('Spent so far in October · day-to-day costs')
  })

  it('handles a finished month and no history', () => {
    const finished = payload([row('2026-09-03', '150.00'), row('2026-10-04', '100.00')], { isPartial: false, asOfDay: 31 })
    const h = headline(pace(frame(finished), finished, 'Household'))
    expect(h.label).toBe('Spent in October')
    expect(h.lines).toEqual([['▼ R$ 50,00 (33%) less than September', 'less']])
    const first = payload([row('2026-10-04', '100.00')])
    expect(headline(pace(frame(first), first, 'Household')).lines)
      .toEqual([['Nothing to compare with yet. Comparisons start in November, against October.', null]])
  })

  it('does not compare a month whose logging started late', () => {
    const late = payload([row('2026-09-29', '449.00'), row('2026-10-02', '100.00')])
    const rows = readRows(late)
    expect(trackedSince(rows)).toBe('2026-10')
    expect(trackedSince(readRows(payload([row('2026-09-06', '1.00')])))).toBe('2026-09')
    const p = pace(byDay(rows), late, 'Household', trackedSince(rows))
    expect(p.has_last).toBe(false)
    expect(headline(p, '', loggingStarted(rows)).lines).toEqual([[
      'Nothing to compare with yet. Logging started on 29 September, so comparisons start in November, against October.',
      null]])
    expect(trackSeries(byDay(rows), late, 'Household', '2026-10').map((s) => s.name)).toEqual(['October so far'])
  })

  it('builds the cards: last, usual and allowance', () => {
    const cs = Object.fromEntries(cards(pace(frame(), SAMPLE, 'Household')).map((c) => [c.key, c]))
    expect(Object.keys(cs)).toEqual(['last', 'usual', 'allowance'])
    expect([cs.last.label, cs.last.value]).toEqual(['Last month · September', 'R$ 600,00'])
    expect(cs.last.lines[0]).toEqual(['R$ 150,00 of it by the 10th', null])
    expect(cs.usual.lines[0]).toEqual(['The average of July–September', null])
    expect(cs.allowance.label).toBe('To stay within the usual month')
    expect(cs.allowance.value).toBe('R$ 4,76 a day')
    expect(cs.allowance.lines[1]).toEqual(['75% of the usual month spent, 32% of the month gone', 'more'])
  })

  it('says when already past the usual month', () => {
    const over = payload([...SAMPLE.rows, row('2026-10-05', '500.00')])
    const card = cards(pace(frame(over), over, 'Household')).at(-1)!
    expect([card.label, card.value]).toEqual(['Past the usual month', 'R$ 400,00'])
  })

  it('counts days for a finished month', () => {
    const finished = payload(SAMPLE.rows, { isPartial: false, asOfDay: 31 })
    const card = cards(pace(frame(finished), finished, 'Household')).at(-1)!
    expect([card.key, card.value]).toEqual(['days', '2 of 31'])
  })

  it('compares each month over the same days', () => {
    const hist = Object.fromEntries(history(frame(), SAMPLE, 'Household').map((h) => [h.month, h]))
    expect(Object.keys(hist)).toEqual(MONTHS)
    expect([hist['2026-09'].total, hist['2026-09'].to_day]).toEqual([60000, 15000])
    expect([hist['2026-10'].per_day, hist['2026-10'].is_selected]).toEqual([3000, true])
  })

  it('needs three months for the usual month', () => {
    const short = payload([row('2026-09-03', '150.00'), row('2026-10-01', '80.00')])
    expect(pace(frame(short), short, 'Household').usual_total).toBeNull()
    const usual = trackSeries(frame(), SAMPLE, 'Household').find((s) => s.role === 'usual')!
    expect(usual.values).toHaveLength(31)
    expect(usual.values[30]).toBe(40000) // September's 30 days carry on to the 31st
  })
})

describe('the calendar', () => {
  it('lays out states and future days', () => {
    const cal = calendarDays(frame(), '2026-10', 'Household', '2026-10-10')
    expect([cal[0].weekday, cal[0].week, cal[0].amount]).toEqual([3, 0, 8000]) // 1 Oct 2026 is a Thursday
    expect(cal[9].state).toBe('today')
    expect([cal[10].state, cal[10].amount, cal[10].count]).toEqual(['future', 0, 0])
    expect(cal[3].top_category).toBe('Pets')
    expect(Math.max(...cal.map((d) => d.week))).toBe(4)
    expect(cal[0].label).toBe('Thursday 1 October')
  })

  it('ignores one huge day in its scale', () => {
    const amounts = Array.from({ length: 31 }, (_, i) => (i + 1 === 5 ? 190000 : (i + 1) % 2 ? 5000 : 0))
    expect(calendarScaleMax(amounts)).toBe(5000)
    expect(calendarScaleMax(new Array(31).fill(0))).toBe(100)
  })
})

describe('where the money goes', () => {
  it('ranks the biggest days with their top category', () => {
    const top = biggestDays(frame(), '2026-10', 'Household')
    expect(top.map((d) => d.key)).toEqual(['2026-10-04', '2026-10-01'])
    expect(top.map((d) => d.name)).toEqual(['Sun 4 Oct', 'Thu 1 Oct'])
    expect(top.map((d) => d.text)).toEqual(['R$ 220 · Pets', 'R$ 80 · Food'])
    expect(top.reduce((a, d) => a + d.share, 0)).toBeCloseTo(1)
    expect(biggestDays(frame(), '2026-10', 'Household', 1).map((d) => d.key)).toEqual(['2026-10-04'])
  })

  it('shares a month by category and a day by item', () => {
    const rows = readRows(payload([row('2026-10-01', '60.00'), row('2026-10-01', '20.00', 'Food', 'Delivery'),
      row('2026-10-04', '220.00', 'Pets', 'Vet'), row('2026-09-04', '999.00', 'Pets', 'Vet')]))
    const mix = ranked(rows, 'Household', 'primary_category', { month: '2026-10' })
    expect(mix.map((m) => m.key)).toEqual(['Pets', 'Food'])
    expect(mix.map((m) => m.text)).toEqual(['R$ 220 · 73%', 'R$ 80 · 27%'])
    const day = ranked(rows, 'My share', 'item', { date: '2026-10-01' })
    expect(day.map((d) => d.name)).toEqual(['Food › Groceries', 'Food › Delivery'])
    expect(day.map((d) => d.amount)).toEqual([3600, 1200])
    expect(ranked(rows, 'Household', 'primary_category', { month: '2026-11' })).toEqual([])
  })

  it("lists a day's purchases biggest first", () => {
    const item = { transaction_timestamp: '2026-10-05T12:30:00Z', primary_category: 'Food', sub_category: 'Groceries',
      price: '100.00', mine: '60.00', payment_method: 'Pix', institution: 'Nubank', paid_by: 'Her' }
    const items = [item, { transaction_timestamp: '2026-10-05T18:00:00Z', primary_category: 'Pets', sub_category: 'Food',
      price: '300.00', mine: '180.00', payment_method: 'Cash', institution: null, paid_by: 'Me' }, item]
    const out = dayItems(items, 'Household')
    expect(out.map((i) => i.name)).toEqual(['Pets › Food · 15:00', 'Groceries · 09:30', 'Groceries · 09:30 (2)'])
    expect(out.map((i) => i.text)).toEqual(['R$ 300 · 60%', 'R$ 100 · 20%', 'R$ 100 · 20%'])
    expect(out[1].detail).toBe('Pix · Nubank, paid by Her')
    expect(dayItems(items, 'My share').map((i) => i.amount)).toEqual([18000, 6000, 6000])
    expect(dayItems([], 'Household')).toEqual([])
  })

  it('adds last month by the same day as a tick', () => {
    const rows = readRows(SAMPLE)
    const bullet = againstLastMonth(ranked(rows, 'Household', 'primary_category', { month: '2026-10' }), rows,
      'Household', 'primary_category', '2026-10', 10)
    expect(Object.fromEntries(bullet.map((b) => [b.name, b.previous]))).toEqual({ Pets: 0, Food: 15000 })
    expect(bullet.map((b) => b.text)).toEqual(['R$ 220 · new', 'R$ 80 · ▼ 47%'])
  })

  it('handles an empty payload', () => {
    const empty = payload([])
    expect(byDay(readRows(empty))).toEqual([])
    expect(biggestDays([], '2026-10', 'Household')).toEqual([])
    expect(ranked([], 'Household', 'primary_category', { month: '2026-10' })).toEqual([])
  })
})

describe('a partly logged last month: shown for context, never a verdict', () => {
  const PARTLY = payload([row('2026-09-28', '300.00'), row('2026-09-30', '100.00'), row('2026-10-02', '50.00'),
    row('2026-10-05', '70.00')], { months: ['2026-09', '2026-10'] })

  it('knows when a month was logged in part', () => {
    expect(partlyLoggedFrom('2026-09', '2026-10', '2026-09-28')).toBe(28)
    expect(partlyLoggedFrom('2026-09', '2026-09', '2026-09-03')).toBeNull()
    expect(partlyLoggedFrom('2026-08', '2026-10', '2026-09-28')).toBeNull()
  })

  it('draws and names it but does not compare', () => {
    const rows = readRows(PARTLY)
    const days = byDay(rows)
    const since = trackedSince(rows)
    const started = loggingStarted(rows)
    const p = pace(days, PARTLY, 'Household', since, started)
    expect([p.has_last, p.last_partly_from, p.last_total]).toEqual([false, 28, 40000])
    const head = headline(p, '', started)
    expect(head.lines.map(([t]) => t)).toEqual(['September: R$ 400,00, logged from the 28th only',
      'Comparisons start in November, against October.'])
    expect(head.lines.every(([, tone]) => tone === null)).toBe(true)
    const last = cards(p).find((c) => c.key === 'last')!
    expect(last.value).toBe('R$ 400,00')
    expect(last.lines[0][0]).toContain('Logged only from the 28th')
    const series = trackSeries(days, PARTLY, 'Household', since, started)
    expect(series[1].name).toBe('September (from the 28th)')
    expect(Math.max(...series[1].values)).toBe(40000)
    expect(trackSeries(days, PARTLY, 'Household', since).map((s) => s.role)).toEqual(['this'])
  })
})

describe('the named comparisons', () => {
  function yearOfData() {
    const months = Array.from({ length: 14 }, (_, i) => addMonths('2026-10', -(13 - i)))
    const rows = months.flatMap((m) => [row(`${m}-01`, '100.00'), row(`${m}-05`, '1000.00', 'Housing', 'Rent', 'Fixed')])
    return payload(rows, { months: months.slice(1) })
  }

  it('needs every month of a comparison logged in full', () => {
    const p = yearOfData()
    const days = frame(p)
    expect(baselineMonths(days, p, 'last', '2025-09')).toEqual(['2026-09'])
    expect(baselineMonths(days, p, 'usual', '2025-09')).toEqual(['2026-09', '2026-08', '2026-07'])
    expect(baselineMonths(days, p, 'year', '2025-09')).toHaveLength(12)
    expect(baselineMonths(days, p, 'last_year', '2025-09')).toEqual(['2025-10'])
    expect(baselineMonths(days, p, 'year', '2026-03')).toEqual([])
    expect(baselineMonths(days, p, 'last_year', '2026-03')).toEqual([])
  })

  it('draws every comparison with data and the target pace', () => {
    const p = yearOfData()
    const series = trackSeries(frame(p), p, 'Household', '2025-09', null, 310000)
    expect(series.map((s) => s.role)).toEqual(['this', 'last', 'usual', 'year', 'last_year', 'target'])
    expect(series.map((s) => s.name)).toEqual(['October so far', 'September', 'Usual month', '12-month average',
      'Same month last year', 'Target'])
    const target = series.at(-1)!.values
    expect([target[0], target[30]]).toEqual([10000, 310000])
    expect(series[0].values).toHaveLength(10)
    expect(Math.max(...series[0].values)).toBe(110000)
  })

  it('totals the months and their references', () => {
    const p = yearOfData()
    const months = monthsFrame(frame(p), p, 'Household', '2025-09')
    expect(months).toHaveLength(13)
    expect(months.at(-1)!.is_partial).toBe(true)
    expect(monthReferences(frame(p), p, 'Household', '2025-09', 300000)).toEqual([['12-month average', 110000],
      ['Target', 300000]])
    expect(monthReferences(frame(p), p, 'Household', '2026-03')).toEqual([])
  })

  it('totals the targets of what is counted', () => {
    const rows = readRows(payload([row('2026-10-02', '10.00')]))
    const targets = new Map([['Food', 300000], ['Pets', 80000]])
    expect(targetTotal(targets, rows, false)).toBe(380000)
    expect(targetTotal(targets, rows, true)).toBe(300000)
    expect(targetTotal(new Map(), rows, false)).toBe(0)
  })
})
