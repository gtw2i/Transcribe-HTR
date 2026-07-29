import { useAppStore } from '../../store/appStore.js'
import { Expander } from '../shared/Expander.jsx'
import { pct } from './format.js'

/**
 * Per-attempt consistency scores and outlier diagnostics (§11, §12, §19).
 *
 * Sortable, so the user can identify the attempts closest to and furthest from
 * the group, and from the consensus (§19). Clicking a row sets the shared focus
 * that highlights the same attempt in both heat maps.
 */

const OUTLIER_BADGE = {
  none: null,
  possible: { cls: 'badge-warn', text: 'possible outlier' },
  strong: { cls: 'badge-error', text: 'strong outlier' },
}

const COLUMNS = [
  { key: 'label', label: 'Attempt', numeric: false },
  { key: 'meanCer', label: 'Mean CER', numeric: true },
  { key: 'medianCer', label: 'Median CER', numeric: true },
  { key: 'minCer', label: 'Min CER', numeric: true },
  { key: 'maxCer', label: 'Max CER', numeric: true },
  { key: 'meanWer', label: 'Mean WER', numeric: true },
  { key: 'medianWer', label: 'Median WER', numeric: true },
  { key: 'cerVsConsensus', label: 'CER vs consensus', numeric: true },
  { key: 'werVsConsensus', label: 'WER vs consensus', numeric: true },
]

export function PerAttemptTable({ report, labels }) {
  const { focusAttemptId, sortKey } = useAppStore((s) => s.consistency)
  const setConsistency = useAppStore((s) => s.setConsistency)

  const results = report.results
  const verdicts = Object.fromEntries(
    results.outliers.verdicts.map((v) => [v.attempt_id, v]),
  )
  const consensus = Object.fromEntries(
    (results.consensus_comparison ?? []).map((c) => [c.attempt_id, c]),
  )

  const rows = results.per_attempt.map((stat) => ({
    id: stat.attempt_id,
    label: labels[stat.attempt_id] ?? stat.attempt_id,
    meanCer: stat.mean_cer,
    medianCer: stat.median_cer,
    minCer: stat.min_cer,
    maxCer: stat.max_cer,
    meanWer: stat.mean_wer,
    medianWer: stat.median_wer,
    cerVsConsensus: consensus[stat.attempt_id]?.cer_vs_consensus ?? null,
    werVsConsensus: consensus[stat.attempt_id]?.wer_vs_consensus ?? null,
    verdict: verdicts[stat.attempt_id],
  }))

  const sorted = [...rows].sort((a, b) => {
    if (sortKey === 'label') return a.label.localeCompare(b.label)
    const av = a[sortKey]
    const bv = b[sortKey]
    if (av === null) return 1
    if (bv === null) return -1
    return av - bv
  })

  const flagged = results.outliers.verdicts.filter((v) => v.is_flagged)

  return (
    <section className="consistency-section">
      <h3>5. Per-attempt consistency</h3>
      <p className="consistency-note">
        Each attempt&apos;s disagreement with all the others. Click a row to
        highlight it in the heat maps.
      </p>

      <div className="table-scroll">
        <table className="consistency-table">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={sortKey === col.key ? 'is-sorted' : ''}
                  onClick={() => setConsistency({ sortKey: col.key })}
                >
                  {col.label}
                </th>
              ))}
              <th style={{ cursor: 'default' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const badge = OUTLIER_BADGE[row.verdict?.status ?? 'none']
              return (
                <tr
                  key={row.id}
                  className={focusAttemptId === row.id ? 'is-focused' : ''}
                  onClick={() =>
                    setConsistency({
                      focusAttemptId: focusAttemptId === row.id ? null : row.id,
                    })
                  }
                >
                  <td>{row.label}</td>
                  <td>{pct(row.meanCer)}</td>
                  <td>{pct(row.medianCer)}</td>
                  <td>{pct(row.minCer)}</td>
                  <td>{pct(row.maxCer)}</td>
                  <td>{pct(row.meanWer)}</td>
                  <td>{pct(row.medianWer)}</td>
                  <td>{pct(row.cerVsConsensus)}</td>
                  <td>{pct(row.werVsConsensus)}</td>
                  <td style={{ textAlign: 'left' }}>
                    {badge ? <span className={`badge ${badge.cls}`}>{badge.text}</span> : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <h4 style={{ marginTop: 'var(--space-4)', marginBottom: 'var(--space-2)' }}>
        Outlier diagnostics
      </h4>

      {!results.outliers.applicable ? (
        <p className="consistency-note">{results.outliers.note}</p>
      ) : flagged.length === 0 ? (
        <p className="consistency-note">
          No attempt shows substantially greater disagreement with the others than
          the group as a whole.
        </p>
      ) : (
        flagged.map((verdict) => (
          <div key={verdict.attempt_id} style={{ marginBottom: 'var(--space-2)' }}>
            <p style={{ margin: 0 }}>{verdict.message}</p>
            {verdict.notes.map((note) => (
              <p key={note} className="consistency-note">{note}</p>
            ))}
          </div>
        ))
      )}

      <Expander title="Why an attempt might differ — and why this is not a verdict">
        <p>{results.outliers.disclaimer}</p>
        <ul>
          {results.outliers.alternative_explanations.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <p className="consistency-note">{results.outliers.note}</p>
      </Expander>
    </section>
  )
}
