import { useAppStore } from '../../store/appStore.js'
import { useAttemptText } from '../../hooks/useConsistency.js'
import { Button } from '../shared/Button.jsx'
import { Alert } from '../shared/Alert.jsx'

/**
 * Transcription selection (§3).
 *
 * Every attempt the document has is listed, including degenerate ones and
 * previously generated consensus records, so the user can see what data exists
 * and what has been left out (§3.2). Only healthy independent attempts are
 * checked to begin with.
 */

const HEALTH_BADGE = {
  ok: null,
  near_empty: { cls: 'badge-warn', text: 'nearly empty' },
  empty: { cls: 'badge-error', text: 'empty output' },
  error_text: { cls: 'badge-error', text: 'error message' },
  corrupt: { cls: 'badge-error', text: 'corrupt text' },
  duplicate_record: { cls: 'badge-muted', text: 'duplicate record' },
}

function AttemptInspector({ root, attemptId, normProfile, tokenizer }) {
  const { data, isLoading, error } = useAttemptText(root, attemptId, normProfile, tokenizer)

  if (isLoading) return <p className="consistency-note">Loading transcription…</p>
  if (error) return <Alert type="error">Could not load this transcription.</Alert>

  return (
    <>
      <p className="consistency-note">
        {data.word_count} words · {data.char_count} characters after normalization
      </p>
      <div className="consensus-text">{data.text}</div>
    </>
  )
}

export function AttemptSelector({ root, attempts, defaultSelection, selectedIds, normProfile, tokenizer }) {
  const consistency = useAppStore((s) => s.consistency)
  const setConsistency = useAppStore((s) => s.setConsistency)
  const toggleAttempt = useAppStore((s) => s.toggleConsistencyAttempt)

  const selectable = attempts.filter((a) => a.is_replicate)
  const selectedCount = selectedIds.length
  const isSubset = selectedCount < selectable.length

  return (
    <section className="consistency-section">
      <h3>1. Transcription attempts</h3>
      <p className="consistency-note">
        {attempts.length} available · {selectedCount} selected
        {isSubset && ' — results below use a subset of the available attempts'}
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-2)', margin: 'var(--space-2) 0' }}>
        <Button
          size="sm"
          onClick={() => setConsistency({ selectedIds: selectable.map((a) => a.attempt_id) })}
        >
          Select all
        </Button>
        <Button size="sm" onClick={() => setConsistency({ selectedIds: [] })}>
          Clear all
        </Button>
        <Button size="sm" onClick={() => setConsistency({ selectedIds: defaultSelection })}>
          Reset to default
        </Button>
      </div>

      <div>
        {attempts.map((attempt) => {
          const badge = HEALTH_BADGE[attempt.health?.status] ?? null
          const isConsensus = attempt.source_type === 'consensus'
          const checked = selectedIds.includes(attempt.attempt_id)
          const focused = consistency.focusAttemptId === attempt.attempt_id
          const open = consistency.inspectId === attempt.attempt_id

          return (
            <div
              key={attempt.attempt_id}
              className={[
                'attempt-row',
                focused ? 'is-focused' : '',
                attempt.is_replicate ? '' : 'is-unavailable',
              ].filter(Boolean).join(' ')}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={!attempt.is_replicate}
                onChange={() => toggleAttempt(attempt.attempt_id, defaultSelection)}
                aria-label={`Include ${attempt.label}`}
                style={{ marginTop: 4 }}
              />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className="attempt-label">{attempt.label}</span>
                  {isConsensus && (
                    <span className="badge badge-info">consensus — not an independent attempt</span>
                  )}
                  {badge && <span className={`badge ${badge.cls}`}>{badge.text}</span>}
                  {attempt.health?.identical_to?.length > 0 && (
                    <span className="badge badge-muted">
                      identical text to {attempt.health.identical_to.length} other
                    </span>
                  )}
                  {attempt.edited_in_session && (
                    <span className="badge badge-warn">edited, unsaved</span>
                  )}
                </div>

                <div className="attempt-meta">
                  {attempt.model && <span>{attempt.model}</span>}
                  {attempt.provider && <span>{attempt.provider}</span>}
                  {attempt.profile_name && <span>{attempt.profile_name}</span>}
                  {attempt.created_at && <span>{attempt.created_at.replace('T', ' ').replace('Z', '')}</span>}
                  <span>{attempt.char_count} chars</span>
                </div>

                {attempt.health?.reasons?.length > 0 && (
                  <p className="consistency-note">{attempt.health.reasons.join('; ')}</p>
                )}

                <Button
                  size="sm"
                  variant="secondary"
                  style={{ marginTop: 'var(--space-1)' }}
                  onClick={() =>
                    setConsistency({ inspectId: open ? null : attempt.attempt_id })
                  }
                >
                  {open ? 'Hide text' : 'Inspect text'}
                </Button>

                {open && (
                  <div style={{ marginTop: 'var(--space-2)' }}>
                    <AttemptInspector
                      root={root}
                      attemptId={attempt.attempt_id}
                      normProfile={normProfile}
                      tokenizer={tokenizer}
                    />
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {selectedCount < 2 && (
        <div style={{ marginTop: 'var(--space-2)' }}>
          <Alert type="warning">
            Select at least two transcription attempts to analyze.
          </Alert>
        </div>
      )}
    </section>
  )
}
