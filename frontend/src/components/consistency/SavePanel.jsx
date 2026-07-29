import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteSaved, listSaved, saveAnalysis } from '../../api/consistency.js'
import { useAppStore } from '../../store/appStore.js'
import { Alert } from '../shared/Alert.jsx'
import { Button } from '../shared/Button.jsx'
import { Expander } from '../shared/Expander.jsx'
import { pct } from './format.js'

/**
 * Explicit save, and the list of previously saved analyses (D11).
 *
 * Running an analysis never writes anything. The first pass at a document often
 * includes an attempt the user only recognises as bad after seeing the heat map,
 * so saving waits for a decision. Saving is additive: re-running after an
 * exclusion and saving again produces a second record rather than replacing the
 * first, and each record carries the attempts it included and excluded.
 */
export function SavePanel({ root, selectedIds }) {
  const { normProfile, tokenizer } = useAppStore((s) => s.consistency)
  const queryClient = useQueryClient()
  const [note, setNote] = useState('')
  const [confirmingId, setConfirmingId] = useState(null)
  const [saved, setSaved] = useState(false)

  const savedList = useQuery({
    queryKey: ['consistency', 'saved', root],
    queryFn: () => listSaved(root),
    enabled: !!root,
    staleTime: 5_000,
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      saveAnalysis({
        root,
        attempt_ids: selectedIds,
        normalization_profile: normProfile,
        tokenizer,
        user_note: note,
      }),
    onSuccess: () => {
      setSaved(true)
      setNote('')
      queryClient.invalidateQueries({ queryKey: ['consistency', 'saved', root] })
      setTimeout(() => setSaved(false), 4000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (analysisId) => deleteSaved(root, analysisId),
    onSuccess: () => {
      setConfirmingId(null)
      queryClient.invalidateQueries({ queryKey: ['consistency', 'saved', root] })
    },
  })

  const analyses = savedList.data?.analyses ?? []

  return (
    <section className="consistency-section">
      <h3>12. Save this analysis</h3>

      {saved ? (
        <Alert type="success">Analysis saved to the document record.</Alert>
      ) : (
        <p className="consistency-note">
          Not saved — this analysis exists only in this session. Saving is
          additive and never replaces an earlier one.
        </p>
      )}

      <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
        <div style={{ flex: '1 1 320px' }}>
          <label htmlFor="save-note" style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
            Note (optional)
          </label>
          <input
            id="save-note"
            className="form-control"
            type="text"
            value={note}
            placeholder="e.g. excluded Run 4 — empty output"
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <Button
          variant="primary"
          disabled={saveMutation.isPending || selectedIds.length < 2}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? 'Saving…' : '💾 Save analysis'}
        </Button>
      </div>

      {saveMutation.isError && (
        <div style={{ marginTop: 'var(--space-2)' }}>
          <Alert type="error">The analysis could not be saved.</Alert>
        </div>
      )}

      <Expander
        title={`Previously saved analyses (${analyses.length})`}
        className="mt-2"
        defaultOpen={analyses.length > 0}
      >
        {analyses.length === 0 ? (
          <p className="consistency-note">
            None saved yet for this document.
          </p>
        ) : (
          <div className="table-scroll">
            <table className="consistency-table">
              <thead>
                <tr>
                  <th style={{ cursor: 'default' }}>Saved</th>
                  <th style={{ cursor: 'default' }}>Attempts</th>
                  <th style={{ cursor: 'default' }}>Median CER</th>
                  <th style={{ cursor: 'default' }}>Median WER</th>
                  <th style={{ cursor: 'default' }}>Profile</th>
                  <th style={{ cursor: 'default' }}>Note</th>
                  <th style={{ cursor: 'default' }} />
                </tr>
              </thead>
              <tbody>
                {analyses.map((record) => (
                  <tr key={record.analysis_id}>
                    <td>{(record.saved_at ?? '').replace('T', ' ').replace('Z', '')}</td>
                    <td>{record.n_attempts}</td>
                    <td>{pct(record.median_cer)}</td>
                    <td>{pct(record.median_wer)}</td>
                    <td style={{ textAlign: 'left' }}>{record.normalization_profile}</td>
                    <td style={{ textAlign: 'left' }}>{record.user_note || '—'}</td>
                    <td>
                      {confirmingId === record.analysis_id ? (
                        <span style={{ display: 'inline-flex', gap: 'var(--space-1)' }}>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => deleteMutation.mutate(record.analysis_id)}
                          >
                            Confirm
                          </Button>
                          <Button size="sm" onClick={() => setConfirmingId(null)}>
                            Cancel
                          </Button>
                        </span>
                      ) : (
                        <Button size="sm" onClick={() => setConfirmingId(record.analysis_id)}>
                          🗑 Delete
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Expander>
    </section>
  )
}
