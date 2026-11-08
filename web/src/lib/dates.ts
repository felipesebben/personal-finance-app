/**
 * Dates in São Paulo time, where every month and day in the app lives.
 * Months are "YYYY-MM" strings and days "YYYY-MM-DD", as the API sends them.
 */
export const TZ = 'America/Sao_Paulo'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December']

/** Today's São Paulo date as "YYYY-MM-DD" (`now` is injectable for tests). */
export function todayIso(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })
    .format(now)
}

/** This São Paulo month as "YYYY-MM". */
export function thisMonth(now: Date = new Date()): string {
  return todayIso(now).slice(0, 7)
}

/** The current São Paulo wall-clock time as "HH:MM". */
export function nowTime(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false })
    .format(now)
}

/** "2026-10" moved by `delta` months: addMonths("2026-01", -1) → "2025-12". */
export function addMonths(month: string, delta: number): string {
  const y = Number(month.slice(0, 4))
  const m = Number(month.slice(5, 7)) - 1 + delta
  const year = y + Math.floor(m / 12)
  const mm = ((m % 12) + 12) % 12
  return `${year}-${String(mm + 1).padStart(2, '0')}`
}

/** Months from `start` to `end` inclusive, oldest first. */
export function monthRange(start: string, end: string): string[] {
  const out: string[] = []
  for (let m = start; m <= end; m = addMonths(m, 1)) out.push(m)
  return out
}

/** The last `count` months ending at `end` (default this month), newest first. */
export function recentMonths(count = 12, end: string = thisMonth()): string[] {
  return Array.from({ length: count }, (_, i) => addMonths(end, -i))
}

export function daysInMonth(month: string): number {
  return new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0)).getUTCDate()
}

/** "October 2026", or "Oct 26" when short. */
export function monthLabel(month: string, short = false): string {
  const name = MONTHS[Number(month.slice(5, 7)) - 1]
  return short ? `${name.slice(0, 3)} ${month.slice(2, 4)}` : `${name} ${month.slice(0, 4)}`
}

/** "October" alone. */
export function monthName(month: string): string {
  return MONTHS[Number(month.slice(5, 7)) - 1]
}

/** "1st", "2nd", "23rd". */
export function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${s}`
}

/** ISO weekday of a "YYYY-MM-DD" day: Monday = 1 … Sunday = 7. */
export function weekday(day: string): number {
  const d = new Date(`${day}T12:00:00Z`).getUTCDay()
  return d === 0 ? 7 : d
}

/** A timestamp from the API (UTC or with offset) shown in São Paulo: "07/11/2026 14:05". */
export function formatTimestamp(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return new Intl.DateTimeFormat('pt-BR', {
    timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(d)
}

/** The São Paulo day of an API timestamp, "YYYY-MM-DD". */
export function dayOf(iso: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return todayIso(d)
}

/** "2026-11-07" + "14:05" as a São Paulo timestamp the API accepts ("2026-11-07T14:05:00-03:00"). */
export function saoPauloTimestamp(day: string, time: string): string {
  // São Paulo has had no daylight saving since 2019: always UTC−3.
  return `${day}T${time.length === 5 ? `${time}:00` : time}-03:00`
}

/** "7 Nov" for a "YYYY-MM-DD" day. */
export function shortDay(day: string): string {
  return `${Number(day.slice(8, 10))} ${MONTHS[Number(day.slice(5, 7)) - 1].slice(0, 3)}`
}
