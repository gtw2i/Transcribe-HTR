import { useAppStore } from '../../store/appStore.js'
import { Alert } from '../shared/Alert.jsx'
import { Expander } from '../shared/Expander.jsx'
import { pct } from './format.js'

/**
 * The consensus transcriptions (§13–§17).
 *
 * §16 requires the three kinds be clearly distinguished, so each carries its own
 * badge and its own explanation of what it actually is:
 *
 *   🅰  most representative existing attempt — verbatim text, nothing synthesized
 *   ⚙   deterministic consensus — assembled by voting, reproducible, no model
 *   🤖  LLM consensus — generated rather than observed (not yet available)
 */

const KINDS = [
  { id: 'medoid', icon: '🅰', label: 'Most representative attempt' },
  { id: 'deterministic', icon: '⚙', label: 'Deterministic consensus' },
  { id: 'llm', icon: '🤖', label: 'LLM consensus' },
]

function SupportedText({ consensus }) {
  return (
    <p className="consensus-text">
      {consensus.tokens.map((token, index) => (
        <span
          key={`${token.token}-${index}`}
          className={token.low_support ? 'consensus-token-low' : undefined}
          title={`supported by ${pct(token.support, 0)} of attempts`}
        >
          {token.token}{' '}
        </span>
      ))}
    </p>
  )
}

export function ConsensusPanel({ report, labels, attemptTexts }) {
  const consensusKind = useAppStore((s) => s.consistency.consensusKind)
  const setConsistency = useAppStore((s) => s.setConsistency)

  const results = report.results
  const consensus = results.consensus
  const medoidId = results.medoid_attempt_id

  if (!consensus) {
    return (
      <section className="consistency-section">
        <h3>6. Consensus</h3>
        <p className="consistency-note">No consensus was computed for this analysis.</p>
      </section>
    )
  }

  return (
    <section className="consistency-section">
      <h3>6. Consensus</h3>

      <div className="consensus-kinds">
        {KINDS.map((kind) => (
          <button
            key={kind.id}
            type="button"
            className={`btn ${consensusKind === kind.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setConsistency({ consensusKind: kind.id })}
            disabled={kind.id === 'llm'}
            title={kind.id === 'llm' ? 'Not yet available' : undefined}
          >
            {kind.icon} {kind.label}
          </button>
        ))}
      </div>

      {consensusKind === 'medoid' && (
        <>
          <p>
            Most representative existing transcription:{' '}
            <strong>{labels[medoidId] ?? medoidId}</strong>
          </p>
          <p className="consistency-note">
            This is the attempt with the lowest aggregate disagreement with the
            others. It is not synthesized — every word is text one transcription
            attempt actually produced.
          </p>
          {results.medoid && (
            <p className="consistency-note">
              Mean disagreement with the rest of the group: {pct(results.medoid.mean_cer)} CER,
              {' '}{pct(results.medoid.mean_wer)} WER.
            </p>
          )}
          {attemptTexts?.[medoidId] && (
            <div className="consensus-text">{attemptTexts[medoidId]}</div>
          )}
        </>
      )}

      {consensusKind === 'deterministic' && (
        <>
          <p className="consistency-note">
            Assembled by aligning every selected attempt to the most representative
            one and taking a majority vote at each word. Reproducible, and it uses
            no generative model — the same attempts always give the same result.
          </p>
          <p className="consistency-note">
            Method <code>{consensus.method}</code> · backbone{' '}
            {labels[consensus.backbone_attempt_id] ?? consensus.backbone_attempt_id} ·
            mean support {pct(consensus.mean_support, 0)} ·{' '}
            {consensus.n_low_support} of {consensus.n_tokens} words below{' '}
            {pct(consensus.low_support_threshold, 0)} support
          </p>

          {consensus.warnings.map((warning) => (
            <div key={warning} style={{ marginBottom: 'var(--space-2)' }}>
              <Alert type="warning">{warning}</Alert>
            </div>
          ))}

          <SupportedText consensus={consensus} />
          <p className="consistency-note">
            Shaded words are supported by fewer than{' '}
            {pct(consensus.low_support_threshold, 0)} of the attempts.
          </p>

          <Expander title="Known limitations of this method">
            <ul>
              {consensus.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </Expander>
        </>
      )}

      {consensusKind === 'llm' && (
        <Alert type="info">
          LLM consensus is not yet available. When it is, it will be marked as
          generated rather than observed, and it will not replace the deterministic
          consensus.
        </Alert>
      )}
    </section>
  )
}
