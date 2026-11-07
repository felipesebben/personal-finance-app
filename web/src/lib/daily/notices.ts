/**
 * In-app notices for the month in progress: a category past its monthly
 * target, one close to it with days still to go, and a recurring bill whose
 * usual day has passed without it being logged. Shown at the top of This
 * month, never pushed to a phone. Port of notices.py; amounts in cents.
 */
import { ordinal } from '../dates'
import { formatBrl } from '../money'
import type { Line } from './shaping'

export const NEAR = 0.9 // "close to its target" from 90% of it

/**
 * Lines, the most urgent first: past their target (tone "more"), then
 * within 10% of it with days to go, then recurring bills (`due`) whose usual
 * day is before today. `spent` is this month so far by category (or label).
 */
export function notices(targets: Map<string, number>, spent: Map<string, number>,
  due: { name: string; amount: number; day: number }[], day: number, days: number): Line[] {
  const over: [number, string][] = []
  const near: [number, string][] = []
  for (const [name, target] of targets) {
    if (target <= 0) continue
    const value = spent.get(name) ?? 0
    const ratio = value / target
    if (ratio > 1) over.push([ratio, `${name} is past its monthly target: ${formatBrl(value)} of ${formatBrl(target)}.`])
    else if (ratio >= NEAR && day < days) {
      near.push([ratio, `${name} is at ${Math.round(ratio * 100)}% of its monthly target with ${days - day} days to go.`])
    }
  }
  const byRatio = (a: [number, string], b: [number, string]) => b[0] - a[0] || b[1].localeCompare(a[1])
  const late: Line[] = [...due].sort((a, b) => a.day - b.day).filter((b) => b.day < day).map((b) => [
    `${b.name.split(' › ').at(-1)} (${formatBrl(b.amount)}) usually comes by the ${ordinal(b.day)} and isn't logged yet.`, null])
  return [
    ...over.sort(byRatio).map(([, t]): Line => [t, 'more']),
    ...near.sort(byRatio).map(([, t]): Line => [t, null]),
    ...late,
  ]
}
