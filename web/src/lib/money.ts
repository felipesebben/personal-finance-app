/**
 * Reading and writing Brazilian reais, as people type and read them.
 *
 * Amounts are integer cents end to end: the API stores Numeric(10, 2) and
 * sends money as decimal strings ("1234.50"), and floats would drift by a
 * cent. `cents()` reads the API's strings, `toApi()` writes them back.
 * Port of the Streamlit frontend's money.py; tests in money.test.ts.
 */

// The API's price is Numeric(10, 2): at most 8 digits before the comma.
const MAX_INTEGER_DIGITS = 8
const GROUPED = /^\d{1,3}(\.\d{3})+$/

/** An API amount ("12.5", "12.50", 12.5, null) as integer cents (null → 0). */
export function cents(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.round(n * 100)
}

/** Integer cents as the API's decimal string: 123456 → "1234.56". */
export function toApi(c: number): string {
  const sign = c < 0 ? '-' : ''
  const abs = Math.abs(Math.round(c))
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

/**
 * Parses what someone typed as an amount in reais into positive cents.
 *
 * Accepts "45", "45,9", "1.234,56", "1234,56", "1234.56", "R$ 12,50" and
 * ",50". When both "." and "," appear, the comma is the decimal separator
 * and the dots must group thousands. With only a dot, it's a decimal point
 * when 1–2 digits follow it ("12.5"), and thousands grouping otherwise
 * ("1.234" is one thousand two hundred and thirty-four, as written in Brazil).
 *
 * @throws Error with a message fit to show the person.
 */
export function parseBrl(text: string): number {
  let s = (text ?? '').replace(/ /g, ' ').trim()
  s = s.replace(/^R\$\s*/i, '').replace(/ /g, '')
  if (!s) throw new Error('Enter an amount, e.g. 45,90')
  if (s.startsWith('-')) throw new Error('The amount must be positive')
  if (!/^[\d.,]+$/.test(s)) throw new Error('Use only digits, with a comma for cents, e.g. 1.234,56')

  let integer: string
  let fraction: string
  if (s.includes(',')) {
    if (s.split(',').length > 2) throw new Error('Use one comma for the cents, e.g. 1.234,56')
    ;[integer, fraction] = s.split(',')
    if (integer.includes('.') && !GROUPED.test(integer)) throw new Error('Dots separate thousands, e.g. 1.234,56')
    integer = integer.replace(/\./g, '')
  } else if (s.includes('.')) {
    const at = s.lastIndexOf('.')
    integer = s.slice(0, at)
    fraction = s.slice(at + 1)
    const dots = s.split('.').length - 1
    if ((fraction.length === 1 || fraction.length === 2) && dots === 1) {
      // "12.5" / "1234.56": a decimal point
    } else if (GROUPED.test(s)) {
      integer = s.replace(/\./g, '')
      fraction = ''
    } else {
      throw new Error('Use a comma for cents, e.g. 1.234,56')
    }
  } else {
    integer = s
    fraction = ''
  }

  if (fraction.length > 2) throw new Error('Use at most two digits for cents')
  integer = integer || '0'
  if (!/^\d*$/.test(integer) || !/^\d*$/.test(fraction)) {
    throw new Error('Use only digits, with a comma for cents, e.g. 1.234,56')
  }
  if (integer.replace(/^0+/, '').length > MAX_INTEGER_DIGITS) throw new Error('That amount is too large')

  const value = Number(integer) * 100 + Number((fraction + '00').slice(0, 2))
  if (value <= 0) throw new Error('The amount must be greater than zero')
  return value
}

/** Cents the Brazilian way: 123450 → "R$ 1.234,50"; negatives keep their sign: "-R$ 12,00". */
export function formatBrl(c: number, symbol = true): string {
  const rounded = Math.round(c)
  const sign = rounded < 0 ? '-' : ''
  const abs = Math.abs(rounded)
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  const text = `${whole},${String(abs % 100).padStart(2, '0')}`
  return symbol ? `${sign}R$ ${text}` : `${sign}${text}`
}

/** Short, for chart labels: "R$ 820", "R$ 4,1 mil", "R$ 1,2 mi". */
export function shortBrl(c: number): string {
  const reais = c / 100
  const sign = reais < 0 ? '-' : ''
  const abs = Math.abs(reais)
  const one = (n: number) => n.toFixed(1).replace('.', ',').replace(/,0$/, '')
  if (abs >= 1_000_000) return `${sign}R$ ${one(abs / 1_000_000)} mi`
  if (abs >= 1_000) return `${sign}R$ ${one(abs / 1_000)} mil`
  return `${sign}R$ ${Math.round(abs)}`
}

/** A signed amount: "+R$ 12,00", "-R$ 3,50", "R$ 0,00". */
export function signedBrl(c: number): string {
  const text = formatBrl(c)
  return c > 0 ? `+${text}` : text
}

/** A share as people read it: 0.6 → "60%", 0.625 → "62,5%". */
export function pctText(fraction: number, digits = 1): string {
  const n = Number((fraction * 100).toFixed(digits))
  return `${String(n).replace('.', ',')}%`
}

/**
 * The first and last installment of `total` paid in `count` parts, by the
 * rule the ETL's cashflow datasource uses: every installment but the last
 * is rounded down to the cent, and the last takes the remainder.
 * installmentAmounts(4000, 3) → [1333, 1334]
 */
export function installmentAmounts(total: number, count: number): [number, number] {
  if (count < 1) throw new Error('count must be at least 1')
  const each = Math.floor(total / count)
  return [each, total - each * (count - 1)]
}

/**
 * How the API will split `total` cents across [user_id, fraction] pairs,
 * mirroring backend/split_logic.split_amount: pairs ordered by user_id, each
 * share but the last rounded half up to the cent, the last absorbing the
 * remainder. Pairs with a zero fraction are dropped.
 */
export function splitLikeBackend(total: number, shares: [number, number][]): Map<number, number> {
  const pairs = shares.filter(([, pct]) => pct > 0).sort((a, b) => a[0] - b[0])
  const out = new Map<number, number>()
  if (!pairs.length) return out
  let used = 0
  pairs.slice(0, -1).forEach(([uid, pct]) => {
    const amount = Math.round(total * pct + 1e-9)
    out.set(uid, amount)
    used += amount
  })
  out.set(pairs[pairs.length - 1][0], total - used)
  return out
}

/**
 * One line read back under the price field, so a typo is caught before
 * saving: "R$ 1.200,00 · 10x R$ 120,00 · your share 60% = R$ 720,00".
 * The installment part appears only above 1x and names the last installment
 * when it differs; the share part only when `shares` names `me`.
 */
export function entryPreview(
  price: number,
  installments = 1,
  shares: [number, number][] | null = null,
  me: number | null = null,
): string {
  const parts = [formatBrl(price)]
  if (installments > 1) {
    const [first, last] = installmentAmounts(price, installments)
    let text = `${installments}x ${formatBrl(first)}`
    if (last !== first) text += ` (last ${formatBrl(last)})`
    parts.push(text)
  }
  if (shares && me !== null) {
    const mine = new Map(shares)
    if (mine.has(me)) {
      const amount = splitLikeBackend(price, shares).get(me) ?? 0
      const pct = String(Number(((mine.get(me) ?? 0) * 100).toFixed(4))).replace('.', ',')
      parts.push(`your share ${pct}% = ${formatBrl(amount)}`)
    }
  }
  return parts.join(' · ')
}
