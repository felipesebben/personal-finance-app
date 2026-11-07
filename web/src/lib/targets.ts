/**
 * The household's monthly targets (GET /category_targets/) as the views use
 * them. A target is for a whole primary category (`sub_category` null) or
 * for one sub-category of it, e.g. Pets › Grooming after deciding on half
 * as many sessions. The two stand apart: a sub-category's target is a
 * decision to follow, not a slice of its category's. Amounts in cents.
 */
import { cents } from './money'

export const SEPARATOR = ' › '

export interface TargetRow {
  primary_category: string
  sub_category: string | null
  amount: string
  updated_at?: string | null
}

/** 'Pets' or 'Pets › Grooming': how a target is named in Settings and in notices. */
export function label(primary: string, sub?: string | null): string {
  return sub ? `${primary}${SEPARATOR}${sub}` : primary
}

/** label() read back: 'Pets › Grooming' → ['Pets', 'Grooming']; 'Pets' → ['Pets', null]. */
export function splitLabel(text: string): [string, string | null] {
  const at = text.indexOf(SEPARATOR)
  return at < 0 ? [text, null] : [text.slice(0, at), text.slice(at + SEPARATOR.length) || null]
}

/** Targets for whole primary categories, by name, in cents. */
export function whole(rows: TargetRow[] | null | undefined): Map<string, number> {
  const out = new Map<string, number>()
  for (const t of rows ?? []) if (!t.sub_category) out.set(t.primary_category, cents(t.amount))
  return out
}

/** Sub-category targets by sub-category name for one primary category (or all, keyed by label()). */
export function subs(rows: TargetRow[] | null | undefined, primary?: string): Map<string, number> {
  const out = new Map<string, number>()
  for (const t of rows ?? []) {
    if (!t.sub_category) continue
    if (primary === undefined) out.set(label(t.primary_category, t.sub_category), cents(t.amount))
    else if (t.primary_category === primary) out.set(t.sub_category, cents(t.amount))
  }
  return out
}
