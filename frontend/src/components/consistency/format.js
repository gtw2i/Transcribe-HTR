/** Formatting helpers shared across the consistency views. */

/** Render a disagreement fraction as a percentage, or an em dash if undefined. */
export function pct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}
