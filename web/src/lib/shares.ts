/**
 * Share inputs that fill each other in: change one person's % and the other
 * person's becomes the rest, so a split is one edit instead of two.
 */

/**
 * The shares after `changed` was edited: the one other person takes `total`
 * minus the new value (never below 0). With more people, the one other person
 * who still has a share (0 = not in the household, as in Settings); if
 * there's no single such person, nothing else changes.
 */
export function fillRest(values: Record<number, number>, changed: number, total = 100): Record<number, number> {
  let others = Object.keys(values).map(Number).filter((k) => k !== changed)
  if (others.length !== 1) others = others.filter((k) => values[k])
  if (others.length !== 1) return { ...values }
  return { ...values, [others[0]]: Math.max(total - (values[changed] ?? 0), 0) }
}
