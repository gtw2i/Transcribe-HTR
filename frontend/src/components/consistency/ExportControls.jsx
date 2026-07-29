import { useState } from 'react'
import { exportBundle } from '../../api/consistency.js'
import { useAppStore } from '../../store/appStore.js'
import { Alert } from '../shared/Alert.jsx'
import { Button } from '../shared/Button.jsx'

/**
 * Export controls (§26).
 *
 * Works on the analysis currently on screen and does not require it to have
 * been saved — a user may only want the CSVs.
 */

const SECTIONS = [
  { id: 'all', label: 'Everything (ZIP)', hint: 'Record, tables, texts and figures' },
  { id: 'numerical', label: 'Tables (CSV)', hint: 'Matrices, per-attempt and summary statistics' },
  { id: 'figures', label: 'Figures', hint: 'Heat maps at 300 dpi, PNG and SVG' },
  { id: 'text', label: 'Texts', hint: 'Consensus and the texts actually measured' },
  { id: 'json', label: 'Record (JSON)', hint: 'The complete machine-readable analysis' },
]

export function ExportControls({ root, selectedIds }) {
  const { normProfile, tokenizer } = useAppStore((s) => s.consistency)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const download = async (section) => {
    setBusy(section)
    setError(null)
    try {
      await exportBundle({
        root,
        attempt_ids: selectedIds,
        normalization_profile: normProfile,
        tokenizer,
        section,
      })
    } catch {
      setError('The export could not be built.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="consistency-section">
      <h3>11. Export</h3>
      <p className="consistency-note">
        CSV for statistical software, JSON for programmatic reuse, PNG and SVG at
        300 dpi for publication. Every file derives from the JSON record, which
        carries the settings needed to reproduce the analysis.
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
        {SECTIONS.map((section) => (
          <Button
            key={section.id}
            variant={section.id === 'all' ? 'primary' : 'secondary'}
            size="sm"
            disabled={busy !== null}
            title={section.hint}
            onClick={() => download(section.id)}
          >
            {busy === section.id ? 'Building…' : section.label}
          </Button>
        ))}
      </div>

      {error && (
        <div style={{ marginTop: 'var(--space-2)' }}>
          <Alert type="error">{error}</Alert>
        </div>
      )}
    </section>
  )
}
