/**
 * The monthly recap you review together: a month in a few sentences — the
 * total and how it compares, what drove the change (day-to-day or fixed, and
 * the biggest moves), and the targets — before settling up. Built from
 * /analytics/shared rows for the household's shared spending at full price.
 * A ▲/▼ only against months logged in full. Port of recap_shaping.py.
 */
import { monthName } from './dates'
import { formatBrl } from './money'
import {
  biggestChanges, compare, compareTotal, monthLabel, ordinal, partlyLoggedFrom, previousFullAverage, shiftMonth,
  trackedSince, lensColumn, type Lens, type Line, type Row,
} from './overview/shaping'

const COST_NAMES: Record<string, string> = { Variable: 'day-to-day', Fixed: 'fixed' }

const pct0 = (x: number) => `${Math.round(x * 100)}%`

/** '▲ R$ 1.858,23 (36%) more than September', toned. */
function moved(change: number, against: string, previous: number | null = null): Line {
  if (change === 0) return [`The same as ${against}`, null]
  const [word, arrow, tone] = change > 0 ? ['more', '▲', 'more' as const] : ['less', '▼', 'less' as const]
  const p = previous ? ` (${pct0(Math.abs(change) / previous)})` : ''
  return [`${arrow} ${formatBrl(Math.abs(change))}${p} ${word} than ${against}`, tone]
}

export interface MonthRecap {
  label: string
  total: string
  lines: Line[]
  causes: Line[]
  moves: Line[]
  targets: Line[]
}

export function monthRecap(rows: Row[], months: string[], month: string, isPartial: boolean,
  firstDate: string | null | undefined, targets: Map<string, number> = new Map(), lens: Lens = 'Household'): MonthRecap {
  const previous = shiftMonth(month, -1)
  const earliest = rows.length ? rows.reduce((m, r) => (r.month < m ? r.month : m), rows[0].month) : null
  const since = trackedSince(firstDate) ?? earliest
  const comparable = since !== null && since <= previous
  const total = compareTotal(rows, month, isPartial, lens)
  const previousName = monthName(previous)
  const byDay = isPartial ? ' by the same day' : ''

  const lines: Line[] = []
  if (comparable) {
    lines.push(moved(total.change, `${previousName}${byDay}`, total.previous))
    const usual = previousFullAverage(rows, months, month, lens, 3, isPartial, since)
    if (usual !== null) lines.push(moved(total.current - usual, `the usual month${byDay}`, usual))
  } else {
    const partly = partlyLoggedFrom(previous, firstDate)
    lines.push([partly
      ? `${previousName} was logged from the ${ordinal(partly)} only, so not compared yet.`
      : 'Nothing to compare with yet: the first whole month logged comes first.', null])
  }

  const causes: Line[] = []
  const moves: Line[] = []
  if (comparable) {
    const split = compare(rows, month, isPartial, lens, 'cost_type')
      .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
    for (const row of split) {
      if (row.change === 0) continue
      const name = COST_NAMES[row.key] ?? row.key.toLowerCase()
      causes.push([`${name[0].toUpperCase()}${name.slice(1)}: ${row.change > 0 ? '▲' : '▼'} ` +
        `${formatBrl(Math.abs(row.change))}, now ${formatBrl(row.current)}`, row.change > 0 ? 'more' : 'less'])
    }
    for (const row of biggestChanges(compare(rows, month, isPartial, lens)).slice(0, 3)) {
      const p = row.pct === null ? '' : ` (${pct0(Math.abs(row.pct))})`
      moves.push([`${row.key} ${row.change > 0 ? '▲' : '▼'} ${formatBrl(Math.abs(row.change))}${p}`,
        row.change > 0 ? 'more' : 'less'])
    }
  }

  const col = lensColumn(lens)
  const spent = new Map<string, number>()
  for (const r of rows) if (r.month === month) spent.set(r.primary_category, (spent.get(r.primary_category) ?? 0) + r[col])
  const targeted = [...targets.entries()].filter(([, t]) => t > 0)
    .map(([name, target]) => ({ name, target, value: spent.get(name) ?? 0, ratio: (spent.get(name) ?? 0) / target }))
    .sort((a, b) => b.ratio - a.ratio || b.name.localeCompare(a.name))
  const targetLines: Line[] = targeted.map((t) => t.ratio > 1
    ? [`${t.name}: ${formatBrl(t.value)} of ${formatBrl(t.target)}, ▲ ${formatBrl(t.value - t.target)} over`, 'more']
    : [`${t.name}: ${formatBrl(t.value)} of ${formatBrl(t.target)} (${pct0(t.ratio)})`, null])

  return {
    label: `${monthLabel(month)}${isPartial ? ' so far' : ''}`,
    total: formatBrl(total.current),
    lines,
    causes,
    moves,
    targets: targetLines,
  }
}
