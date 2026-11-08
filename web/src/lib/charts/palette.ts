/**
 * Chart palette and anatomy, shared by every chart.
 *
 * The colours are the CSS tokens in app.css (var(--…)), so charts follow the
 * light and dark themes. One job per colour: brand green marks the household
 * and what's picked (lighter green for the rest); orange = spent more, blue =
 * spent less, and they never encode plain magnitude. Grey is for comparisons
 * (last month's tick), ink for targets.
 *
 * Anatomy, after Apple's chart guidelines: the data is the most prominent
 * thing, axes and grid stay quiet (hairline grid, light labels, few ticks in
 * familiar steps), the y labels sit inside the plot on the leading edge so
 * the chart lines up with the card's text and the plot gets the full width,
 * values are labelled directly rather than through a legend, and the whole
 * plot area is the hit target for reading values.
 */
export const BRAND = 'var(--brand)'
export const BRAND_LIGHT = 'var(--brand-light)'
export const BRAND_PALE = 'var(--brand-pale)'
export const MORE = 'var(--more)'
export const LESS = 'var(--less)'
export const INK = 'var(--ink)'
export const INK_2 = 'var(--ink-2)'
export const MUTED = 'var(--muted)'
export const GREY = 'var(--compare-2)'
/** Comparison lines (last month, the usual month): grey, told apart by dash. */
export const COMPARE = 'var(--compare)'
export const AXIS = 'var(--axis)'
export const GRID = 'var(--grid)'

/** Height of one ranked bar row, and of an x axis under it (heights are rows + axis). */
export const BAR_ROW = 36
export const X_AXIS = 22
/** The chart slot in a KPI card. */
export const SPARK_HEIGHT = 68

/** Rough width of a label in px at the 12px chart font (for the names column). */
export function textWidth(text: string, px = 12): number {
  return Math.ceil(text.length * px * 0.58)
}

/** Shortens a label to `max` characters with an ellipsis. */
export function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/**
 * A bar as an SVG path: square where it meets the axis, rounded only at its
 * far end (`end`: the side the value grows towards), as Apple's charts draw
 * them. The radius never exceeds half the bar's thickness or its length.
 */
export function barPath(x: number, y: number, w: number, h: number, r: number, end: 'right' | 'left' | 'top'): string {
  if (w <= 0 || h <= 0) return ''
  const f = (n: number) => Math.round(n * 100) / 100
  if (end === 'top') {
    const k = Math.min(r, w / 2, h)
    return `M${f(x)},${f(y + h)}V${f(y + k)}A${f(k)},${f(k)} 0 0 1 ${f(x + k)},${f(y)}H${f(x + w - k)}`
      + `A${f(k)},${f(k)} 0 0 1 ${f(x + w)},${f(y + k)}V${f(y + h)}Z`
  }
  const k = Math.min(r, h / 2, w)
  if (end === 'right') {
    return `M${f(x)},${f(y)}H${f(x + w - k)}A${f(k)},${f(k)} 0 0 1 ${f(x + w)},${f(y + k)}V${f(y + h - k)}`
      + `A${f(k)},${f(k)} 0 0 1 ${f(x + w - k)},${f(y + h)}H${f(x)}Z`
  }
  return `M${f(x + w)},${f(y)}H${f(x + k)}A${f(k)},${f(k)} 0 0 0 ${f(x)},${f(y + k)}V${f(y + h - k)}`
    + `A${f(k)},${f(k)} 0 0 0 ${f(x + k)},${f(y + h)}H${f(x + w)}Z`
}
