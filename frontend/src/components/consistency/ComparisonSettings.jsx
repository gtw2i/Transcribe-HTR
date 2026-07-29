import { useAppStore } from '../../store/appStore.js'

/**
 * Normalization profile and tokenizer (§4.2, §4.3, §6).
 *
 * A visible control rather than a buried dropdown, with the profile's exact
 * step list shown beneath it — §4.2 requires the default be clearly
 * documented, and comparing `standard_historical` against `diplomatic` on the
 * same document is itself informative: the gap between them is the
 * orthographic share of the disagreement.
 */
export function ComparisonSettings({ options }) {
  const { normProfile, tokenizer } = useAppStore((s) => s.consistency)
  const setConsistency = useAppStore((s) => s.setConsistency)

  if (!options) return null

  const profiles = options.normalization_profiles ?? []
  const current = profiles.find((p) => p.id === normProfile)
  const currentTokenizer = (options.tokenizers ?? []).find((t) => t.id === tokenizer)

  return (
    <section className="consistency-section">
      <h3>2. Comparison settings</h3>

      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        {profiles.map((profile) => (
          <button
            key={profile.id}
            type="button"
            className={`btn ${normProfile === profile.id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => setConsistency({ normProfile: profile.id })}
          >
            {profile.label}
          </button>
        ))}
      </div>

      {current && (
        <>
          <p className="consistency-note">{current.description}</p>
          <p className="consistency-note">
            <strong>Steps:</strong> {current.steps.join(' → ')}
          </p>
        </>
      )}

      <div style={{ marginTop: 'var(--space-3)' }}>
        <label
          htmlFor="consistency-tokenizer"
          style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}
        >
          Word tokenization
        </label>
        <select
          id="consistency-tokenizer"
          className="form-control"
          value={tokenizer}
          onChange={(e) => setConsistency({ tokenizer: e.target.value })}
          style={{ maxWidth: 280 }}
        >
          {(options.tokenizers ?? []).map((t) => (
            <option key={t.id} value={t.id}>{t.id}</option>
          ))}
        </select>
        {currentTokenizer && (
          <p className="consistency-note">{currentTokenizer.description}</p>
        )}
      </div>
    </section>
  )
}
