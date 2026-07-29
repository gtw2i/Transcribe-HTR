import { useAppStore } from '../../store/appStore.js'
import { useDiff } from '../../hooks/useConsistency.js'
import { Alert } from '../shared/Alert.jsx'
import { InlineSpinner } from '../shared/Spinner.jsx'

/**
 * Difference inspection (§18).
 *
 * A disagreement score alone does not say *what* differs, so the aligned
 * segments are rendered side by side with a category breakdown: whether the
 * difference is spelling, punctuation, spacing, an omitted or inserted word, a
 * missing line, or substantial divergence.
 *
 * Both original texts stay available (§18, final clause).
 */

const CONSENSUS_ID = '__consensus__'

function Side({ result, side }) {
  const tokensKey = side === 'a' ? 'a_tokens' : 'b_tokens'

  return (
    <div className="diff-text">
      {result.segments.map((segment, index) => {
        const tokens = segment[tokensKey]
        if (!tokens.length) return null
        const cls =
          segment.tag === 'equal'
            ? 'diff-seg-equal'
            : segment.tag === 'insert'
              ? (side === 'b' ? 'diff-seg-insert' : 'diff-seg-equal')
              : segment.tag === 'delete'
                ? (side === 'a' ? 'diff-seg-delete' : 'diff-seg-equal')
                : 'diff-seg-replace'

        return (
          <span
            key={`${side}-${index}`}
            className={cls}
            title={segment.tag === 'equal' ? undefined : segment.category_label}
          >
            {tokens.join(' ')}{' '}
          </span>
        )
      })}
    </div>
  )
}

export function DiffViewer({ root, report, attempts, labels }) {
  const { diffA, diffB, normProfile, tokenizer } = useAppStore((s) => s.consistency)
  const setConsistency = useAppStore((s) => s.setConsistency)

  const included = report.attempts_included
  const consensusText = report.results.consensus?.text
  const aId = diffA ?? included[0]
  const bId = diffB ?? (consensusText ? CONSENSUS_ID : included[1])

  const texts = consensusText ? { [CONSENSUS_ID]: consensusText } : {}
  const { data: result, isFetching, error } = useDiff(
    { root, aId, bId, texts, normalizationProfile: normProfile, tokenizer },
    true,
  )

  const choices = [
    ...included.map((id) => ({ value: id, label: labels[id] ?? id })),
    ...(consensusText ? [{ value: CONSENSUS_ID, label: 'Deterministic consensus' }] : []),
  ]

  return (
    <section className="consistency-section">
      <h3>8. Difference inspection</h3>

      <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
        <div>
          <label htmlFor="diff-a" style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
            Compare
          </label>
          <select
            id="diff-a"
            className="form-control"
            value={aId}
            onChange={(e) => setConsistency({ diffA: e.target.value })}
          >
            {choices.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="diff-b" style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
            against
          </label>
          <select
            id="diff-b"
            className="form-control"
            value={bId}
            onChange={(e) => setConsistency({ diffB: e.target.value })}
          >
            {choices.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      {aId === bId && (
        <Alert type="info">Choose two different transcriptions to compare.</Alert>
      )}
      {error && <Alert type="error">Could not compute the difference.</Alert>}
      {isFetching && <p className="consistency-note"><InlineSpinner /> Comparing…</p>}

      {result && (
        <>
          <p style={{ marginTop: 0 }}>{result.summary}</p>

          <div className="diff-categories">
            {Object.entries(result.category_counts)
              .filter(([category]) => category !== 'equal')
              .sort((a, b) => b[1] - a[1])
              .map(([category, count]) => (
                <span key={category} className="badge badge-muted">
                  {result.category_labels[category] ?? category}: {count}
                </span>
              ))}
          </div>

          <div className="comparison-columns">
            <div>
              <h4>{labels[aId] ?? (aId === CONSENSUS_ID ? 'Consensus' : aId)}</h4>
              <Side result={result} side="a" />
            </div>
            <div>
              <h4>{labels[bId] ?? (bId === CONSENSUS_ID ? 'Consensus' : bId)}</h4>
              <Side result={result} side="b" />
            </div>
          </div>

          <details style={{ marginTop: 'var(--space-3)' }}>
            <summary style={{ cursor: 'pointer', fontSize: 'var(--font-size-sm)' }}>
              Show the unmodified original text of both
            </summary>
            <div className="comparison-columns" style={{ marginTop: 'var(--space-2)' }}>
              <div>
                <h4>Original — {labels[aId] ?? aId}</h4>
                <div className="consensus-text">{result.a_original}</div>
              </div>
              <div>
                <h4>Original — {labels[bId] ?? bId}</h4>
                <div className="consensus-text">{result.b_original}</div>
              </div>
            </div>
          </details>
        </>
      )}

      <p className="consistency-note">
        {attempts.length} attempts available in this document.
      </p>
    </section>
  )
}
