/**
 * What a view counts: every analysis view (This month and Month by month, on
 * Our expenses and My expenses) can narrow its rows the same way before
 * adding anything up:
 *  - what to count: everything, day-to-day costs (cost type Variable, the
 *    ones a decision this week can change) or fixed costs;
 *  - some primary categories only;
 *  - without one-offs (nature Annual or Extraordinary, like an IPVA or a
 *    repair, which make one month look expensive).
 * Works on any rows with primary_category, cost_type and nature: the
 * /analytics rows, the daily rows and a list of expenses.
 */
export const EVERYTHING = 'Everything'
export const DAY_TO_DAY = 'Day-to-day'
export const FIXED = 'Fixed costs'
export const FOCUSES = [EVERYTHING, DAY_TO_DAY, FIXED] as const
export type Focus = (typeof FOCUSES)[number]
const FOCUS_COST_TYPE: Record<string, string> = { [DAY_TO_DAY]: 'Variable', [FIXED]: 'Fixed' }
export const ONE_OFFS = ['Annual', 'Extraordinary']

export interface Filters {
  focus: Focus
  categories: string[]
  withoutOneOffs: boolean
}

export const NO_FILTERS: Filters = { focus: EVERYTHING, categories: [], withoutOneOffs: false }

export interface Filterable {
  primary_category: string
  cost_type?: string | null
  nature?: string | null
}

export function isActive(f: Filters | null | undefined): boolean {
  return !!f && (f.focus !== EVERYTHING || f.categories.length > 0 || f.withoutOneOffs)
}

/** The rows the filters keep (all of them without filters). */
export function filterRows<T extends Filterable>(rows: T[], f: Filters | null | undefined): T[] {
  if (!f || !isActive(f)) return rows
  const costType = FOCUS_COST_TYPE[f.focus]
  return rows.filter((r) =>
    (!costType || r.cost_type === costType) &&
    (!f.categories.length || f.categories.includes(r.primary_category)) &&
    (!f.withoutOneOffs || !ONE_OFFS.includes(r.nature ?? '')))
}

/** What's being counted, in a few words, or '' for everything: 'day-to-day costs · Food, Pets · without one-offs'. */
export function note(f: Filters | null | undefined): string {
  if (!f) return ''
  const parts: string[] = []
  if (f.focus === DAY_TO_DAY) parts.push('day-to-day costs')
  else if (f.focus === FIXED) parts.push('fixed costs')
  if (f.categories.length) parts.push(f.categories.join(', '))
  if (f.withoutOneOffs) parts.push('without one-offs')
  return parts.join(' · ')
}

/** How many filters inside the Filters popover are on (for its label). */
export function countOn(f: Filters, billed = false): number {
  return f.categories.length + (f.withoutOneOffs ? 1 : 0) + (billed ? 1 : 0)
}
