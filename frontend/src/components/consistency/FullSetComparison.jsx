import { pct } from './format.js'

/**
 * Full set versus filtered (§21).
 *
 * When attempts have been excluded, both analyses are shown together so the
 * user can see whether a single poor transcription accounts for most of the
 * observed variability. The baseline is simply a second cache entry, so keeping
 * it costs nothing and it can never be overwritten by an exclusion (§3.3).
 */
export function FullSetComparison({ baseline, filtered, labels }) {
  if (!baseline || !filtered) return null
  if (baseline.results.n_attempts === filtered.results.n_attempts) return null

  const excluded = filtered.attempts_excluded
    .filter((e) => e.reason === 'user_excluded' || e.reason.startsWith('health:'))
    .map((e) => labels[e.attempt_id] ?? e.attempt_id)

  const rows = [
    ['Median pairwise CER disagreement', 'cer', 'median'],
    ['Median pairwise WER disagreement', 'wer', 'median'],
    ['Mean pairwise CER disagreement', 'cer', 'mean'],
    ['Mean pairwise WER disagreement', 'wer', 'mean'],
  ]

  return (
    <section className="consistency-section">
      <h3>9. Full set versus filtered</h3>
      <p className="consistency-note">
        {excluded.length > 0
          ? `Excluded: ${excluded.join(', ')}.`
          : 'A subset of the available attempts is in use.'}
      </p>

      <div className="table-scroll">
        <table className="consistency-table">
          <thead>
            <tr>
              <th style={{ cursor: 'default' }}>Statistic</th>
              <th style={{ cursor: 'default' }}>
                All {baseline.results.n_attempts} attempts
              </th>
              <th style={{ cursor: 'default' }}>
                {filtered.results.n_attempts} retained
              </th>
              <th style={{ cursor: 'default' }}>Change</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, metric, stat]) => {
              const before = baseline.results[metric][stat]
              const after = filtered.results[metric][stat]
              const delta = after - before
              return (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{pct(before)}</td>
                  <td>{pct(after)}</td>
                  <td style={{ color: delta < 0 ? 'var(--color-success)' : 'var(--color-text-muted)' }}>
                    {delta >= 0 ? '+' : ''}{pct(delta)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="consistency-note">
        A large reduction indicates that the excluded attempts accounted for most
        of the variability among the replicates.
      </p>
    </section>
  )
}
