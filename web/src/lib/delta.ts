/**
 * The one way a KPI says how it moved: short enough for one line under the
 * number on a phone, e.g. "▼ R$ 1,8 mil (39%) vs October". The arrow and the
 * word carry the direction, so colour is never alone; the exact amounts and
 * what's being compared go in the card's (i), not under the number.
 */
import { shortBrl } from './money'

export type Tone = 'more' | 'less' | null
export type DeltaLine = [string, Tone]

/** Change in cents against `against`; `base` (the earlier amount) adds a percentage when it isn't zero. */
export function delta(change: number, base: number | null, against: string): DeltaLine {
  if (Math.abs(change) < 50) return [`Same as ${against}`, null]
  const more = change > 0
  const pct = base ? ` (${Math.round(Math.abs(change / base) * 100)}%)` : ''
  return [`${more ? '▲' : '▼'} ${shortBrl(Math.abs(change))}${pct} vs ${against}`, more ? 'more' : 'less']
}
