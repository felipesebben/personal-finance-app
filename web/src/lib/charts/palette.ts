/**
 * Chart palette and anatomy, shared by every chart (keep in step with app.css).
 *
 * One job per colour: brand green marks the household and what's picked
 * (lighter green for the rest); orange = spent more, blue = spent less, and
 * they never encode plain magnitude. Grey is for comparisons (last month's
 * tick), ink for targets. Every chart: no frame or background, a quiet axis
 * line, hairline grid, muted labels, values labelled directly rather than
 * through a legend, axis titles at the end of their axis.
 */
export const BRAND = '#1f6f5c'
export const BRAND_LIGHT = '#9cc5b7'
export const BRAND_PALE = '#dcece6'
export const MORE = '#b5470f'
export const LESS = '#1f5fa8'
export const INK = '#17201c'
export const INK_2 = '#4d5a53'
export const MUTED = '#6f7a74'
export const GREY = '#b9c0ba'
export const AXIS = '#aab2ac'
export const GRID = '#e9ece8'

/** Height of one ranked bar row, and of an x axis under it (heights are rows + axis). */
export const BAR_ROW = 30
export const X_AXIS = 22
/** The chart slot in a KPI card. */
export const SPARK_HEIGHT = 56

/** Rough width of a label in px at the 12px chart font (for the names column). */
export function textWidth(text: string, px = 12): number {
  return Math.ceil(text.length * px * 0.56)
}

/** Shortens a label to `max` characters with an ellipsis. */
export function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}
