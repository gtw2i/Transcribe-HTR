import { useAppStore } from '../../store/appStore.js'

/**
 * Pairwise disagreement heat map (§8).
 *
 * A plain CSS grid rather than a charting library: the matrix is small by
 * construction (a document's replicate count), every cell is a real DOM node
 * so it can carry a tooltip and a label, and clicking one drives the linked
 * highlighting in the other views (§19).
 *
 * The colour domain is clipped at a high percentile of the off-diagonal values
 * so one extreme pair cannot flatten the rest (§8). Clipping is presentational
 * only — the true value is always shown and always exported. Cells beyond the
 * cap get a distinct "off-scale" treatment.
 */

function formatPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function cellColor(value, vmin, vmax) {
  if (value <= 0) return 'transparent'
  const span = Math.max(vmax - vmin, 1e-9)
  const t = Math.min(Math.max((value - vmin) / span, 0), 1)
  // Single-hue sequential ramp built from the primary token, light = agreement.
  return `rgba(255, 75, 75, ${(0.08 + 0.82 * t).toFixed(3)})`
}

export function HeatMap({ spec, labels, title, caption }) {
  const focusAttemptId = useAppStore((s) => s.consistency.focusAttemptId)
  const setConsistency = useAppStore((s) => s.setConsistency)

  if (!spec) return null

  const ids = spec.attempt_ids
  const labelFor = (id) => labels?.[id] ?? id
  const n = ids.length

  const onFocus = (id) =>
    setConsistency({ focusAttemptId: focusAttemptId === id ? null : id })

  return (
    <figure className="heatmap">
      <figcaption className="heatmap-title">{title}</figcaption>

      <div
        className="heatmap-grid"
        style={{ gridTemplateColumns: `auto repeat(${n}, minmax(44px, 1fr))` }}
        role="table"
        aria-label={title}
      >
        {/* Column headers */}
        <div className="heatmap-corner" aria-hidden="true" />
        {ids.map((id) => (
          <button
            key={`col-${id}`}
            type="button"
            className={`heatmap-head heatmap-head-col${focusAttemptId === id ? ' is-focused' : ''}`}
            onClick={() => onFocus(id)}
            title={labelFor(id)}
          >
            {labelFor(id)}
          </button>
        ))}

        {/* Rows */}
        {ids.map((rowId, i) => (
          <Row
            key={`row-${rowId}`}
            rowId={rowId}
            i={i}
            ids={ids}
            spec={spec}
            labelFor={labelFor}
            focusAttemptId={focusAttemptId}
            onFocus={onFocus}
          />
        ))}
      </div>

      <div className="heatmap-legend">
        <span className="heatmap-scale" aria-hidden="true" />
        <span className="heatmap-scale-labels">
          <span>0%</span>
          <span>{formatPercent(spec.vmax)}</span>
        </span>
        {spec.clipped && (
          <span className="heatmap-offscale-note">
            <span className="heatmap-swatch-offscale" aria-hidden="true" />
            above {formatPercent(spec.vmax)} — highest pair is {formatPercent(spec.raw_max)}
          </span>
        )}
      </div>

      {caption && <p className="heatmap-caption">{caption}</p>}
    </figure>
  )
}

function Row({ rowId, i, ids, spec, labelFor, focusAttemptId, onFocus }) {
  return (
    <>
      <button
        type="button"
        className={`heatmap-head heatmap-head-row${focusAttemptId === rowId ? ' is-focused' : ''}`}
        onClick={() => onFocus(rowId)}
        title={labelFor(rowId)}
      >
        {labelFor(rowId)}
      </button>

      {ids.map((colId, j) => {
        const value = spec.values[i][j]
        const isDiagonal = i === j
        const offScale = !isDiagonal && value > spec.vmax
        const inFocus =
          focusAttemptId && (focusAttemptId === rowId || focusAttemptId === colId)
        const dimmed = focusAttemptId && !inFocus

        const classes = [
          'heatmap-cell',
          isDiagonal ? 'is-diagonal' : '',
          offScale ? 'is-offscale' : '',
          inFocus ? 'is-focused' : '',
          dimmed ? 'is-dimmed' : '',
        ].filter(Boolean).join(' ')

        return (
          <div
            key={`${rowId}-${colId}`}
            className={classes}
            style={
              isDiagonal || offScale
                ? undefined
                : { background: cellColor(value, spec.vmin, spec.vmax) }
            }
            title={
              isDiagonal
                ? `${labelFor(rowId)} compared with itself: 0.0%`
                : `${labelFor(rowId)} ↔ ${labelFor(colId)}: ${formatPercent(value)}`
            }
            aria-label={
              isDiagonal
                ? `${labelFor(rowId)} with itself, zero`
                : `${labelFor(rowId)} and ${labelFor(colId)}, ${formatPercent(value)}`
            }
          >
            {isDiagonal ? '0' : (value * 100).toFixed(1)}
          </div>
        )
      })}
    </>
  )
}
