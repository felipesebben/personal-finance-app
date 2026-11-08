/**
 * Where the money goes, as the analysis views draw it: ranked bars (a grey
 * tick at the comparison, a dark one at the target) with the change beside
 * them. Pure: Where.svelte draws what these return. Amounts in cents.
 */
import { shortBrl } from '../money'

/** A row for charts/RankedBars.svelte. */
export interface Bar {
  label: string
  value: number
  text: string
  tick?: number | null
  target?: number | null
  picked?: boolean
  title?: string
}

export type ChangeMode = 'R$' | '%'
export const MODES: ChangeMode[] = ['R$', '%']

export interface WhereItem {
  name: string
  amount: number
  /** What it cost in the comparison (last month by the same day); null = no comparison. */
  previous?: number | null
  /** Its monthly target, if any. */
  target?: number | null
}

const pct0 = (x: number) => `${Math.round(Math.abs(x) * 100)}%`
const arrow = (c: number) => (c > 0 ? '▲ ' : c < 0 ? '▼ ' : '')

/** The change of one item: its value on the chosen scale and its label ("▲ R$ 220", "▼ 47%", "new"). */
export function change(item: WhereItem, mode: ChangeMode): { value: number | null; text: string } {
  const prev = item.previous ?? 0
  const c = item.amount - prev
  if (mode === '%') {
    if (prev <= 0) return { value: null, text: 'new' }
    return { value: c / prev, text: `${arrow(c)}${pct0(c / prev)}` }
  }
  return { value: c, text: `${arrow(c)}${shortBrl(Math.abs(c))}` }
}

/**
 * The bars and, when there's a comparison, the change rows beside them.
 * `combined` (a narrow screen, where the change can't sit beside its bar)
 * puts the change in the bar's tip text instead: "R$ 1,2 mil · ▲ 33%".
 * Without a comparison the tip gives the share: "R$ 4,1 mil · 59%".
 */
export function whereBars(items: WhereItem[], mode: ChangeMode, picked: string | null, combined: boolean):
  { bars: Bar[]; changes: { label: string; value: number | null; text: string }[] | null } {
  const compared = items.some((i) => i.previous !== null && i.previous !== undefined)
  const total = items.reduce((a, i) => a + i.amount, 0) || 1
  const changes = compared ? items.map((i) => ({ label: i.name, ...change(i, mode) })) : null
  const bars = items.map((i, k): Bar => {
    let text = `${shortBrl(i.amount)} · ${pct0(i.amount / total)}`
    if (changes) text = combined ? `${shortBrl(i.amount)} · ${changes[k].text}` : shortBrl(i.amount)
    return {
      label: i.name, value: i.amount, text, picked: i.name === picked,
      tick: compared && (i.previous ?? 0) > 0 ? i.previous : null,
      target: i.target && i.target > 0 ? i.target : null,
    }
  })
  return { bars, changes: combined ? null : changes }
}
