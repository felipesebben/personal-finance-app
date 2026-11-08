/**
 * Settings' pure logic: turning an edited list (categories, payment methods,
 * pets) into the API calls that apply it, with the plan in sentences and
 * the reasons it can't be saved yet; the household split; and the monthly
 * targets table. Port of frontend/settings_logic.py and shares.py's
 * fill_rest; tests in settings.test.ts.
 */
import * as targets from './targets'
import { addMonths } from './dates'
import { cents, formatBrl, parseBrl, toApi } from './money'
import type { AnalyticsPayload } from './briefing'

export type Row = Record<string, unknown>

export interface Table {
  key: string
  fields: string[]
  required: string[]
  unique: string[]
  label: (r: Row) => string
  choices?: Record<string, string[]>
  flags?: Record<string, [string, string]>
}

export const CATEGORIES: Table = {
  key: 'category_id',
  fields: ['primary_category', 'sub_category', 'cost_type', 'for_pets'],
  required: ['primary_category', 'sub_category', 'cost_type'],
  unique: ['primary_category', 'sub_category'],
  label: (r) => `${r.primary_category} › ${r.sub_category}`,
  choices: { cost_type: ['Variable', 'Fixed'] },
  flags: { for_pets: ['asks which pet', "doesn't ask which pet"] },
}

export const PAYMENT_METHODS: Table = {
  key: 'payment_method_id',
  fields: ['method_name', 'institution', 'is_credit', 'is_joint'],
  required: ['method_name'],
  unique: ['method_name', 'institution'],
  label: (r) => `${r.method_name}${r.institution ? ` · ${r.institution}` : ''}`,
  flags: {
    is_credit: ['credit (offers installments)', 'not credit'],
    is_joint: ['a joint account (nobody owes for it)', 'a personal account'],
  },
}

export const PETS: Table = {
  key: 'pet_id',
  fields: ['name'],
  required: ['name'],
  unique: ['name'],
  label: (r) => String(r.name),
}

export interface Plan {
  adds: Row[]
  updates: [number, Row][]
  deletes: number[]
  lines: string[]
  errors: string[]
}

export const isEmptyPlan = (p: Plan) => !p.adds.length && !p.updates.length && !p.deletes.length

/** Blank cells (null, NaN, "") read as null; text is trimmed. */
export function clean(value: unknown): unknown {
  if (value === null || value === undefined) return null
  if (typeof value === 'number' && Number.isNaN(value)) return null
  if (typeof value === 'string') return value.trim() || null
  return value
}

export function normalise(row: Row, table: Table): Row {
  const out: Row = {}
  for (const f of table.fields) out[f] = clean(row[f])
  for (const flag of Object.keys(table.flags ?? {})) out[flag] = !!out[flag]
  return out
}

function fillBlanks(row: Row): Row {
  return Object.fromEntries(Object.entries(row).map(([k, v]) => [k, v === null ? '…' : v]))
}

function describeUpdate(old: Row, next: Row, table: Table): string {
  const before = table.label(old)
  const after = table.label(next)
  const parts: string[] = []
  if (before !== after) parts.push(`Rename ${before} → ${after}`)
  for (const f of table.fields) {
    if (old[f] === next[f] || table.unique.includes(f)) continue
    const flag = table.flags?.[f]
    if (flag) parts.push(`${after}: ${next[f] ? flag[0] : flag[1]}`)
    else parts.push(`${after}: ${f.replace(/_/g, ' ')} → ${next[f]}`)
  }
  return parts.join('; ')
}

/**
 * `original` is what the API returned (each row has its id and
 * `expense_count`); `edited` the rows afterwards, where added rows have no id.
 */
export function planChanges(original: Row[], edited: Row[], table: Table): Plan {
  const plan: Plan = { adds: [], updates: [], deletes: [], lines: [], errors: [] }
  const before = new Map(original.map((r) => [Number(r[table.key]), r]))
  const kept = new Set<number>()
  const finals: Row[] = []

  for (const raw of edited) {
    const rawId = clean(raw[table.key])
    const row = normalise(raw, table)
    if (table.fields.every((f) => row[f] === null || row[f] === false)) continue
    const missing = table.required.filter((f) => row[f] === null)
    const bad = Object.entries(table.choices ?? {}).filter(([f, allowed]) => row[f] !== null && !allowed.includes(String(row[f])))
    if (missing.length || bad.length) {
      plan.errors.push(`Fill in every column for “${table.label(fillBlanks(row))}”.`)
      continue
    }
    finals.push(row)
    if (rawId === null) {
      plan.adds.push(row)
      plan.lines.push(`Add ${table.label(row)}`)
      continue
    }
    const id = Number(rawId)
    kept.add(id)
    const old = normalise(before.get(id) ?? {}, table)
    const changes: Row = {}
    for (const f of table.fields) if (row[f] !== old[f]) changes[f] = row[f]
    if (Object.keys(changes).length) {
      plan.updates.push([id, changes])
      plan.lines.push(describeUpdate(old, row, table))
    }
  }

  for (const [id, old] of before) {
    if (kept.has(id)) continue
    const name = table.label(normalise(old, table))
    const used = Number(old.expense_count ?? 0)
    if (used) {
      plan.errors.push(`${name} can't be removed: ${used} expense${used !== 1 ? 's' : ''} use it. ` +
        'Rename it instead, or delete those expenses first.')
    } else {
      plan.deletes.push(id)
      plan.lines.push(`Remove ${name}`)
    }
  }

  const seen = new Set<string>()
  for (const row of finals) {
    const k = table.unique.map((f) => String(row[f] ?? '').toLowerCase()).join('\u0000')
    if (seen.has(k)) plan.errors.push(`${table.label(row)} appears twice.`)
    seen.add(k)
  }
  return plan
}

// --- household split ---------------------------------------------------------

/**
 * The split as typed (user_id → percent, 0 = not in the household) to the
 * PUT body, or an error message. Percent to a fraction with four decimals.
 */
export function householdPayload(sharesPct: Map<number, number>): [{ user_id: number; share_pct: number }[], string | null] {
  const members = [...sharesPct].filter(([, pct]) => pct && pct > 0)
  const total = members.reduce((s, [, pct]) => s + pct, 0)
  if (!members.length) return [[], 'Give at least one person a share.']
  if (Math.abs(total - 100) >= 0.01) return [[], `Shares must add up to 100% (now ${Number(total.toFixed(4))}%).`]
  return [members.map(([user_id, pct]) => ({ user_id, share_pct: Number((pct / 100).toFixed(4)) })), null]
}

/**
 * The shares after `changed` was edited: the one other person takes `total`
 * minus the new value (never below 0). With more people, the one other who
 * still has a share; with no single such person, nothing else changes.
 */
export function fillRest<K>(values: Map<K, number>, changed: K, total = 100): Map<K, number> {
  let others = [...values.keys()].filter((k) => k !== changed)
  if (others.length !== 1) others = others.filter((k) => values.get(k))
  const out = new Map(values)
  if (others.length !== 1) return out
  out.set(others[0], Math.max(total - (values.get(changed) ?? 0), 0))
  return out
}

// --- monthly targets -----------------------------------------------------------

const TRACKED_BY_DAY = 7

/** The first month logged in full: that month if logging began by the 7th, else the next. */
export function trackedSince(firstDate: string | null | undefined): string | null {
  if (!firstDate) return null
  const month = firstDate.slice(0, 7)
  return Number(firstDate.slice(8, 10)) <= TRACKED_BY_DAY ? month : addMonths(month, 1)
}

/**
 * A starting target per primary category (and per sub-category, keyed
 * "Primary › Sub", rounded up to R$ 10) from history: the average of the
 * last `n` months logged in full (shared spending at full price, from an
 * /analytics/shared payload ending last month), rounded up to R$ `step`.
 * Returns cents by name, and the months averaged.
 */
export function suggestTargets(analytics: AnalyticsPayload | null | undefined, n = 3, step = 50): [Map<string, number>, string[]] {
  if (!analytics || !analytics.rows?.length) return [new Map(), []]
  const since = trackedSince(analytics.first_date) ?? analytics.rows.map((r) => r.month).sort()[0]
  const months = analytics.months.filter((m) => m >= since).slice(-n)
  if (!months.length) return [new Map(), []]
  const recent = analytics.rows.filter((r) => months.includes(r.month))
  const byPrimary = new Map<string, number>()
  const bySub = new Map<string, number>()
  for (const r of recent) {
    const c = cents(r.household)
    byPrimary.set(r.primary_category, (byPrimary.get(r.primary_category) ?? 0) + c)
    const key = targets.label(r.primary_category, r.sub_category)
    if (r.sub_category) bySub.set(key, (bySub.get(key) ?? 0) + c)
  }
  const out = new Map<string, number>()
  const roundUp = (total: number, unit: number) => Math.ceil(total / months.length / (unit * 100) - 1e-9) * unit * 100
  for (const [c, v] of byPrimary) if (v > 0) out.set(c, roundUp(v, step))
  for (const [c, v] of bySub) if (v > 0) out.set(c, roundUp(v, 10))
  return [out, months]
}

export interface TargetRowView {
  name: string
  target: string
  suggested: string
  sub: boolean
}

/**
 * One row per primary category, A–Z, each followed by its sub-categories:
 * the target as typed text ("3.000,00", blank = none) and the suggestion.
 * With `fill`, a blank whole-category target starts at its suggestion;
 * sub-categories are never filled in (their targets are decisions).
 */
export function targetRows(categories: { primary_category: string; sub_category?: string | null }[],
  rows: targets.TargetRow[] | null | undefined, suggested: Map<string, number> = new Map(), fill = false): TargetRowView[] {
  const current = new Map((rows ?? []).map((t) => [targets.label(t.primary_category, t.sub_category), cents(t.amount)]))
  const subs = new Map<string, Set<string>>()
  for (const c of categories ?? []) {
    if (!subs.has(c.primary_category)) subs.set(c.primary_category, new Set())
    if (c.sub_category) subs.get(c.primary_category)!.add(c.sub_category)
  }
  const byLower = (a: string, b: string) => a.toLowerCase().localeCompare(b.toLowerCase())
  const names = [...subs.keys()].sort(byLower)
    .flatMap((p) => [p, ...[...subs.get(p)!].sort(byLower).map((s) => targets.label(p, s))])
  return names.map((name) => {
    const sub = name.includes(targets.SEPARATOR)
    let target = ''
    if (current.has(name)) target = formatBrl(current.get(name)!, false)
    else if (fill && !sub && suggested.has(name)) target = formatBrl(suggested.get(name)!, false)
    return { name, target, sub, suggested: suggested.has(name) ? formatBrl(suggested.get(name)!) : '—' }
  })
}

/** The edited targets as PUT /category_targets/'s list (blank = no target), and the errors that block saving. */
export function targetsPayload(edited: { name: string; target: string | null }[]):
  [{ primary_category: string; sub_category: string | null; amount: string }[], string[]] {
  const found: { primary_category: string; sub_category: string | null; amount: string }[] = []
  const errors: string[] = []
  for (const { name, target } of edited) {
    const text = (target ?? '').trim()
    if (!text) continue
    let amount: number
    try {
      amount = parseBrl(text)
    } catch (e) {
      errors.push(`${name}: ${(e as Error).message}`)
      continue
    }
    const [primary, sub] = targets.splitLabel(name)
    found.push({ primary_category: primary, sub_category: sub, amount: toApi(amount) })
  }
  return [found, errors]
}
