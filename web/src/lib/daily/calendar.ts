/**
 * This month's calendar: each day shaded by what was spent, from the
 * lightest green to brand green at a typical big day (calendarScaleMax),
 * pale grey with nothing spent. Drawn as a CSS grid by
 * sections/daily/Calendar.svelte, so the squares keep their shape at any width.
 */
import { formatBrl } from '../money'
import type { CalDay } from './shaping'

export const EMPTY_DAY = '#f1f3f0'
export const HEAT = ['#d7ebe2', '#1f6f5c'] as const
export const WEEKDAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
export const WHITE_FROM = 0.55 // share of the scale above which a day's number turns white

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))

/** A day's colour: pale grey with nothing spent, then light green to brand green at `top` or more. */
export function shade(amount: number, top: number): string {
  if (amount <= 0) return EMPTY_DAY
  const t = Math.min(amount / Math.max(top, 1), 1)
  const [a, b] = [rgb(HEAT[0]), rgb(HEAT[1])]
  return `#${a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, '0')).join('')}`
}

/** Whether a day's number should be white (on a dark green). */
export function isDark(amount: number, top: number): boolean {
  return amount > top * WHITE_FROM
}

/** The hover text: "Friday 23 October · R$ 305,00 · 3 expenses · mostly Food". */
export function dayTitle(d: CalDay): string {
  if (d.state === 'future') return d.label
  const parts = [d.label, formatBrl(d.amount)]
  if (d.count) parts.push(`${d.count} expense${d.count !== 1 ? 's' : ''}`)
  if (d.top_category) parts.push(`mostly ${d.top_category}`)
  return parts.join(' · ')
}
