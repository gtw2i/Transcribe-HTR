import { useMemo } from 'react'
import { useAppStore } from '../../store/appStore.js'
import { useRoots } from '../../hooks/useRoots.js'
import {
  useAnalysis,
  useAttempts,
  useBaselineAnalysis,
  useConsistencyOptions,
} from '../../hooks/useConsistency.js'
import { Alert } from '../shared/Alert.jsx'
import { Button } from '../shared/Button.jsx'
import { Expander } from '../shared/Expander.jsx'
import { Spinner } from '../shared/Spinner.jsx'
import { AttemptSelector } from './AttemptSelector.jsx'
import { ComparisonSettings } from './ComparisonSettings.jsx'
import { ConsensusPanel } from './ConsensusPanel.jsx'
import { DiffViewer } from './DiffViewer.jsx'
import { ExportControls } from './ExportControls.jsx'
import { FullSetComparison } from './FullSetComparison.jsx'
import { HeatMap } from './HeatMap.jsx'
import { OverallStats } from './OverallStats.jsx'
import { PerAttemptTable } from './PerAttemptTable.jsx'
import { ResearchSummary } from './ResearchSummary.jsx'
import { SavePanel } from './SavePanel.jsx'

/**
 * Multi-transcription consistency analysis (§20, §31).
 *
 * Treats repeated transcription attempts as replicate measurements and reports
 * how much they disagree. Nothing here measures accuracy — that would need a
 * verified reference transcription (§1, §28).
 */

function buildHeatmapSpec(matrix, ids, percentile) {
  const offDiagonal = []
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = 0; j < ids.length; j += 1) {
      if (i !== j) offDiagonal.push(matrix[i][j])
    }
  }
  const sorted = [...offDiagonal].sort((a, b) => a - b)
  const rawMax = sorted.length ? sorted[sorted.length - 1] : 0
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil((percentile / 100) * sorted.length) - 1),
  )
  const cap = sorted.length ? sorted[index] : 0
  const vmax = Math.max(cap, 1e-4)

  return {
    attempt_ids: ids,
    values: matrix,
    vmin: 0,
    vmax,
    raw_max: rawMax,
    clipped: rawMax > vmax,
  }
}

export function ConsistencyTab() {
  const activeRoot = useAppStore((s) => s.activeRoot)
  const setActiveRoot = useAppStore((s) => s.setActiveRoot)
  const consistency = useAppStore((s) => s.consistency)
  const setConsistency = useAppStore((s) => s.setConsistency)

  const { data: roots } = useRoots()
  const { data: options } = useConsistencyOptions()
  const { data: attemptData, isLoading: attemptsLoading, error: attemptsError } =
    useAttempts(activeRoot)

  const attempts = useMemo(() => attemptData?.attempts ?? [], [attemptData])
  const defaultSelection = useMemo(
    () => attemptData?.default_selection ?? [],
    [attemptData],
  )
  const selectedIds = consistency.selectedIds ?? defaultSelection

  const labels = useMemo(
    () => Object.fromEntries(attempts.map((a) => [a.attempt_id, a.label])),
    [attempts],
  )
  const attemptTexts = useMemo(() => ({}), [])

  const analysisArgs = {
    root: activeRoot,
    attemptIds: selectedIds,
    normalizationProfile: consistency.normProfile,
    tokenizer: consistency.tokenizer,
  }

  const { data: report, isFetching, error } = useAnalysis(analysisArgs, consistency.hasRun)
  const { data: baseline } = useBaselineAnalysis(
    {
      root: activeRoot,
      allIds: defaultSelection,
      normalizationProfile: consistency.normProfile,
      tokenizer: consistency.tokenizer,
    },
    consistency.hasRun,
  )

  const cerSpec = useMemo(() => {
    if (!report) return null
    return buildHeatmapSpec(
      consistency.matrixMode === 'directional'
        ? report.results.matrix_cer_directional
        : report.results.matrix_cer_symmetric,
      report.attempts_included,
      consistency.scaleMode === 'linear' ? 100 : 95,
    )
  }, [report, consistency.matrixMode, consistency.scaleMode])

  const werSpec = useMemo(() => {
    if (!report) return null
    return buildHeatmapSpec(
      consistency.matrixMode === 'directional'
        ? report.results.matrix_wer_directional
        : report.results.matrix_wer_symmetric,
      report.attempts_included,
      consistency.scaleMode === 'linear' ? 100 : 95,
    )
  }, [report, consistency.matrixMode, consistency.scaleMode])

  if (!activeRoot) {
    return (
      <div className="consistency-tab">
        <Alert type="info">
          Select or upload a document first, then return here to compare its
          transcription attempts.
        </Alert>
      </div>
    )
  }

  return (
    <div className="consistency-tab">
      <section className="consistency-section">
        <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 220 }}>
            <label htmlFor="consistency-root" style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>
              Document
            </label>
            <select
              id="consistency-root"
              className="form-control"
              value={activeRoot}
              onChange={(e) => {
                setActiveRoot(e.target.value)
                setConsistency({ selectedIds: null, hasRun: false, focusAttemptId: null })
              }}
            >
              {roots?.map((r) => (
                <option key={r.root} value={r.root}>{r.root}</option>
              ))}
            </select>
          </div>
        </div>

        <Expander title="What this measures — and what it does not" className="mt-2">
          <p>
            This compares repeated transcription attempts with one another and
            reports how much they <strong>disagree</strong>. Consistent attempts
            indicate a reproducible transcription process.
          </p>
          <p>
            It does <strong>not</strong> measure accuracy. Several attempts can
            agree closely and still be wrong in the same way, and an attempt that
            disagrees with the others may be the one that read the manuscript
            correctly. Measuring accuracy requires a verified reference
            transcription, which this analysis does not use.
          </p>
        </Expander>
      </section>

      {attemptsError && (
        <Alert type="error">
          No transcription data for this document yet. Transcribe it first, then
          return here.
        </Alert>
      )}

      {attemptsLoading && <Spinner label="Loading transcription attempts…" />}

      {attemptData && (
        <>
          <AttemptSelector
            root={activeRoot}
            attempts={attempts}
            defaultSelection={defaultSelection}
            selectedIds={selectedIds}
            normProfile={consistency.normProfile}
            tokenizer={consistency.tokenizer}
          />

          <ComparisonSettings options={options} />

          <section className="consistency-section">
            <Button
              variant="primary"
              disabled={selectedIds.length < 2 || isFetching}
              onClick={() => setConsistency({ hasRun: true })}
            >
              {isFetching ? 'Analyzing…' : 'Run consistency analysis'}
            </Button>
            <p className="consistency-note">
              Deterministic — no AI model is used, and nothing is written to the
              document.
            </p>
          </section>
        </>
      )}

      {error && (
        <Alert type="error">
          {error.response?.data?.detail ?? 'The analysis could not be completed.'}
        </Alert>
      )}

      {isFetching && <Spinner label="Computing pairwise comparisons…" />}

      {report && !isFetching && (
        <>
          <OverallStats
            report={report}
            isSubset={report.results.n_attempts < attemptData.n_replicates}
            totalAvailable={attemptData.n_replicates}
          />

          <section className="consistency-section">
            <h3>4. Pairwise heat maps</h3>

            <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginBottom: 'var(--space-3)' }}>
              <Button
                size="sm"
                variant={consistency.matrixMode === 'symmetric' ? 'primary' : 'secondary'}
                onClick={() => setConsistency({ matrixMode: 'symmetric' })}
              >
                Symmetric
              </Button>
              <Button
                size="sm"
                variant={consistency.matrixMode === 'directional' ? 'primary' : 'secondary'}
                onClick={() => setConsistency({ matrixMode: 'directional' })}
              >
                Directional
              </Button>
              <span style={{ width: 'var(--space-3)' }} />
              <Button
                size="sm"
                variant={consistency.scaleMode === 'robust' ? 'primary' : 'secondary'}
                onClick={() => setConsistency({ scaleMode: 'robust' })}
              >
                Robust scale
              </Button>
              <Button
                size="sm"
                variant={consistency.scaleMode === 'linear' ? 'primary' : 'secondary'}
                onClick={() => setConsistency({ scaleMode: 'linear' })}
              >
                Linear scale
              </Button>
            </div>

            {consistency.matrixMode === 'directional' && (
              <p className="consistency-note">
                Row = reference, column = hypothesis. The two directions differ
                only in which transcription&apos;s length is the denominator.
              </p>
            )}

            <div className="heatmap-pair">
              <HeatMap
                spec={cerSpec}
                labels={labels}
                title="Pairwise CER disagreement"
                caption="Character-level disagreement between each pair of attempts."
              />
              <HeatMap
                spec={werSpec}
                labels={labels}
                title="Pairwise WER disagreement"
                caption="Word-level disagreement between each pair of attempts."
              />
            </div>
          </section>

          <PerAttemptTable report={report} labels={labels} />

          <ConsensusPanel report={report} labels={labels} attemptTexts={attemptTexts} />

          <section className="consistency-section">
            <h3>7. Comparison against the consensus</h3>
            <p className="consistency-note">{report.results.consensus_caveat}</p>
            <p className="consistency-note">
              These figures appear in the per-attempt table above, in the two
              rightmost columns.
            </p>
          </section>

          <DiffViewer
            root={activeRoot}
            report={report}
            attempts={attempts}
            labels={labels}
          />

          <FullSetComparison baseline={baseline} filtered={report} labels={labels} />

          <ResearchSummary report={report} />

          <ExportControls root={activeRoot} selectedIds={selectedIds} />

          <SavePanel root={activeRoot} selectedIds={selectedIds} />
        </>
      )}
    </div>
  )
}
