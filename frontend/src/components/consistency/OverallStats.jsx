import { Alert } from '../shared/Alert.jsx'
import { Expander } from '../shared/Expander.jsx'
import { pct } from './format.js'

/**
 * Headline consistency figures (§9, §10).
 *
 * §10 forbids showing an unlabelled "±", so each of the three quantities —
 * central tendency, spread across pairs, and uncertainty in the aggregate —
 * is rendered with its own label, and the uncertainty is omitted entirely
 * (with an explanation) when the sample is too small to support it.
 */

function Metric({ variability, summary }) {
  const uncertainty = variability.uncertainty

  return (
    <div className="stat-block">
      <div className="stat-label">{variability.central.label}</div>
      <div className="stat-value">{pct(variability.central.value)}</div>
      <div className="stat-detail">
        {variability.spread.label}: {pct(variability.spread.low)} – {pct(variability.spread.high)}
        <br />
        {uncertainty.applicable
          ? `${uncertainty.label}: ${pct(uncertainty.value)}`
          : uncertainty.note}
      </div>
      <div className="stat-detail">
        mean {pct(summary.mean)} · SD {pct(variability.spread.sd)} ·
        range {pct(summary.min)} – {pct(summary.max)}
      </div>
    </div>
  )
}

export function OverallStats({ report, isSubset, totalAvailable }) {
  const results = report.results
  const variability = results.variability
  const smallSample = results.small_sample

  return (
    <section className="consistency-section">
      <h3>3. Overall consistency</h3>

      {isSubset && (
        <div style={{ marginBottom: 'var(--space-2)' }}>
          <Alert type="warning">
            Based on {results.n_attempts} of {totalAvailable} available transcription attempts.
          </Alert>
        </div>
      )}

      <p className="consistency-note">
        {results.n_attempts} attempts · {results.n_pairs} unique pairwise comparisons
      </p>

      <div className="stat-row" style={{ marginTop: 'var(--space-3)' }}>
        <Metric variability={variability.cer} summary={results.cer} />
        <Metric variability={variability.wer} summary={results.wer} />
      </div>

      {smallSample.level !== 'adequate' && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          <Alert type="warning">{smallSample.message}</Alert>
        </div>
      )}

      <Expander title="What these error bars mean" className="mt-2">
        <p>{variability.cer.uncertainty.description}</p>
        <p>
          Three separate quantities are reported and should not be confused. The
          headline figure is the <strong>median</strong> disagreement between pairs.
          The <strong>IQR</strong> describes how much the pairs vary among
          themselves. The <strong>jackknife standard error</strong> estimates how
          precisely the average is pinned down, and is computed by leaving out one
          transcription attempt at a time — the attempt is the resampling unit
          because pairwise comparisons share attempts and so are not independent
          observations.
        </p>
        <p>
          All of these describe <strong>consistency between repeated attempts</strong>.
          None of them measures accuracy, which would require a verified reference
          transcription.
        </p>
      </Expander>
    </section>
  )
}
