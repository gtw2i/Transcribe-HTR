import { useState, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { transcribe } from '../../api/transcription.js'
import { runNer, fetchEntityTypes } from '../../api/ner.js'
import { harmonize } from '../../api/harmonization.js'
import { summarize } from '../../api/summarize.js'
import { useAppStore } from '../../store/appStore.js'
import { useProfiles } from '../../hooks/useProfiles.js'
import { useRoots } from '../../hooks/useRoots.js'
import { Button } from '../shared/Button.jsx'
import { TextArea } from '../shared/TextArea.jsx'
import { NumberStepper } from '../shared/NumberStepper.jsx'
import { TwoColumn } from '../shared/TwoColumn.jsx'
import { Expander } from '../shared/Expander.jsx'
import { Alert } from '../shared/Alert.jsx'
import { InlineSpinner } from '../shared/Spinner.jsx'

const DEFAULT_MODELS = {
  Gemini: ['gemini-3.1-pro-preview', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash'],
  OpenAI: ['gpt-5.5', 'gpt-5', 'gpt-4o', 'gpt-4o-mini'],
  Anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5'],
}

function TooltipIcon({ title }) {
  return (
    <span title={title} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 16, height: 16, borderRadius: '50%',
      border: '1px solid var(--color-border)', fontSize: 10,
      color: 'var(--color-text-muted)', cursor: 'help', marginLeft: 4,
    }}>?</span>
  )
}

const SUBSECTION_HEADING = {
  fontWeight: 700,
  fontSize: 'var(--font-size-lg)',
  color: 'var(--color-heading)',
  marginBottom: 'var(--space-3)',
}

function NerEntityTypeEditor({ types, onChange, disabled = false }) {
  const [inputVal, setInputVal] = useState('')

  const addType = (raw) => {
    const trimmed = raw.trim().toLowerCase()
    if (!trimmed || types.includes(trimmed)) return
    onChange([...types, trimmed])
  }

  const removeType = (type) => onChange(types.filter((t) => t !== type))

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addType(inputVal)
      setInputVal('')
    }
  }

  return (
    <div style={{ marginTop: 'var(--space-2)', marginLeft: 'var(--space-4)', opacity: disabled ? 0.45 : 1, pointerEvents: disabled ? 'none' : 'auto' }}>
      <label style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', display: 'block', marginBottom: 'var(--space-1)' }}>
        Entity Types
      </label>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)',
        padding: 'var(--space-2)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius)', background: 'var(--color-bg)',
        alignItems: 'center', minHeight: 36, maxWidth: 320,
      }}>
        {types.map((type) => (
          <span key={type} style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 'var(--radius)',
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            fontSize: 'var(--font-size-sm)', lineHeight: 1.4,
          }}>
            {type}
            <button
              type="button"
              onClick={() => removeType(type)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '0 0 0 2px', lineHeight: 1,
                color: 'var(--color-text-muted)', fontSize: 12,
              }}
              aria-label={`Remove ${type}`}
            >×</button>
          </span>
        ))}
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add type…"
          style={{
            border: 'none', outline: 'none', background: 'transparent',
            fontSize: 'var(--font-size-sm)', minWidth: 80, flex: 1,
            color: 'var(--color-text)',
          }}
        />
      </div>
    </div>
  )
}

function ProfileSelector() {
  const activeProfile = useAppStore((s) => s.activeProfile)
  const setActiveProfile = useAppStore((s) => s.setActiveProfile)
  const openProfileEditor = useAppStore((s) => s.openProfileEditor)

  const { data: profiles } = useProfiles()

  const active = profiles?.find((p) => p.slug === activeProfile)
  const templates = (profiles || []).filter((p) => p.template)
  const userProfiles = (profiles || []).filter((p) => !p.template)

  return (
    <div className="form-group">
      <div style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-start' }}>
        <div style={{ flex: '0 0 50%' }}>
          <label htmlFor="profile-select" style={{ margin: 0 }}>Transcription Profile</label>

          <select
            id="profile-select"
            className="form-control"
            value={activeProfile}
            onChange={(e) => setActiveProfile(e.target.value)}
          >
            {templates.length > 0 && (
              <optgroup label="Built-in Templates">
                {templates.map((p) => (
                  <option key={p.slug} value={p.slug}>{p.name}</option>
                ))}
              </optgroup>
            )}
            {userProfiles.length > 0 && (
              <optgroup label="My Profiles">
                {userProfiles.map((p) => (
                  <option key={p.slug} value={p.slug}>{p.name}</option>
                ))}
              </optgroup>
            )}
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            <Button variant="secondary" size="sm"
              onClick={() => openProfileEditor(active?.template ? 'clone' : 'edit', activeProfile)}>
              ✏️ Edit
            </Button>
            <Button variant="secondary" size="sm" onClick={() => openProfileEditor('new', null)}>
              + New
            </Button>
          </div>
        </div>

        {active?.description && (
          <div style={{ flex: 1 }}>
            <label style={{ margin: 0 }}>Description</label>
            <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginTop: 4 }}>
              {active.description}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function DocumentSection({ roots, selectedRoots, onToggle, onSelectAll, onSelectNone }) {
  if (!roots || roots.length === 0) {
    return (
      <Alert type="info">📤 Upload documents in the Upload tab first.</Alert>
    )
  }

  return (
    <div className="section">
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
        <div className="section-title" style={{ margin: 0 }}>
          Documents ({selectedRoots.size} of {roots.length} selected)
        </div>
        <Button variant="ghost" size="sm" onClick={onSelectAll}>All</Button>
        <Button variant="ghost" size="sm" onClick={onSelectNone}>None</Button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {roots.map((r) => (
            <tr key={r.root} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ padding: 'var(--space-2) var(--space-2) var(--space-2) 0', width: 24 }}>
                <input
                  type="checkbox"
                  checked={selectedRoots.has(r.root)}
                  onChange={() => onToggle(r.root)}
                />
              </td>
              <td style={{ padding: 'var(--space-2)', fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-sm)' }}>
                {r.root}
              </td>
              <td style={{ padding: 'var(--space-2) 0', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', textAlign: 'right' }}>
                {r.run_count > 0
                  ? `${r.run_count} run${r.run_count !== 1 ? 's' : ''}`
                  : 'not yet transcribed'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TranscriptionTab() {
  const domainKnowledge = useAppStore((s) => s.domainKnowledge)
  const setDomainKnowledge = useAppStore((s) => s.setDomainKnowledge)
  const selectedProvider = useAppStore((s) => s.selectedProvider)
  const selectedModel = useAppStore((s) => s.selectedModel)
  const openaiApiKey = useAppStore((s) => s.openaiApiKey)
  const geminiApiKey = useAppStore((s) => s.geminiApiKey)
  const anthropicApiKey = useAppStore((s) => s.anthropicApiKey)
  const nResponses = useAppStore((s) => s.nResponses)
  const nerEnabled = useAppStore((s) => s.nerEnabled)
  const nerEntityTypes = useAppStore((s) => s.nerEntityTypes)
  const setNResponses = useAppStore((s) => s.setNResponses)
  const setNerEnabled = useAppStore((s) => s.setNerEnabled)
  const setNerEntityTypes = useAppStore((s) => s.setNerEntityTypes)
  const activeProfile = useAppStore((s) => s.activeProfile)
  const setTranscriptionResults = useAppStore((s) => s.setTranscriptionResults)
  const setActiveRootOnly = useAppStore((s) => s.setActiveRootOnly)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const setNerResult = useAppStore((s) => s.setNerResult)
  const setNerError = useAppStore((s) => s.setNerError)
  const transcriptionBatch = useAppStore((s) => s.transcriptionBatch)
  const setTranscriptionBatch = useAppStore((s) => s.setTranscriptionBatch)
  const clearTranscriptionBatch = useAppStore((s) => s.clearTranscriptionBatch)
  const autoHarmonize = useAppStore((s) => s.autoHarmonize)
  const setAutoHarmonize = useAppStore((s) => s.setAutoHarmonize)
  const harmonizationResult = useAppStore((s) => s.harmonizationResult)
  const setHarmonizationResult = useAppStore((s) => s.setHarmonizationResult)
  const nerResult = useAppStore((s) => s.nerResult)
  const autoSummarize = useAppStore((s) => s.autoSummarize)
  const setAutoSummarize = useAppStore((s) => s.setAutoSummarize)
  const summaryResult = useAppStore((s) => s.summaryResult)
  const setSummaryResult = useAppStore((s) => s.setSummaryResult)

  const queryClient = useQueryClient()
  const { data: roots } = useRoots()

  // Track which roots are selected; auto-add newly uploaded roots
  const [selectedRoots, setSelectedRoots] = useState(new Set())
  const knownRootsRef = useRef(new Set())

  useEffect(() => {
    if (!roots) return
    const newRoots = roots.filter((r) => !knownRootsRef.current.has(r.root))
    if (newRoots.length === 0) return
    newRoots.forEach((r) => knownRootsRef.current.add(r.root))
    setSelectedRoots((prev) => {
      const next = new Set(prev)
      newRoots.forEach((r) => next.add(r.root))
      return next
    })
  }, [roots])

  useEffect(() => {
    fetchEntityTypes().then(setNerEntityTypes).catch(() => {})
  }, [])

  const apiKey = selectedProvider === 'OpenAI' ? openaiApiKey : selectedProvider === 'Anthropic' ? anthropicApiKey : geminiApiKey
  const batchRunning = transcriptionBatch !== null && transcriptionBatch.currentRoot !== null

  const buildParams = (root) => ({
    root,
    model: selectedModel || DEFAULT_MODELS[selectedProvider]?.[0] || '',
    provider: selectedProvider,
    openai_api_key: openaiApiKey,
    gemini_api_key: geminiApiKey,
    anthropic_api_key: anthropicApiKey,
    n_responses: nResponses,
    domain_knowledge: domainKnowledge,
    source_choice: 'Call API',
    profile_name: activeProfile,
  })

  const handleTranscribe = async () => {
    if (!roots || selectedRoots.size === 0 || !apiKey) return

    const targets = (roots || []).filter((r) => selectedRoots.has(r.root))
    const nerEnabledNow = nerEnabled

    const initialDocProgress = {}
    targets.forEach((r) => {
      initialDocProgress[r.root] = {
        transcribeVariant: 0,
        transcribeTotal: nResponses,
        transcribeDone: false,
        nerDone: false,
        nerEnabled: nerEnabledNow,
        tokensUsage: null,
        nerTokensUsage: null,
        error: null,
      }
    })

    setTranscriptionBatch({
      targets: targets.map((r) => r.root),
      total: targets.length,
      completed: 0,
      currentRoot: targets[0]?.root,
      errors: [],
      nerRunning: false,
      startTime: Date.now(),
      endTime: null,
      docProgress: initialDocProgress,
      autoHarmonize,
      harmonizeRunning: false,
      harmonizeDone: false,
      harmonizeTokens: null,
      harmonizeError: null,
      autoSummarize,
      summarizeRunning: false,
      summarizeDone: false,
      summarizeTokens: null,
      summarizeError: null,
    })

    for (const r of targets) {
      setTranscriptionBatch((prev) => prev && ({ ...prev, currentRoot: r.root, nerRunning: false }))

      const accumulatedOutputs = []
      const aggregatedTokens = { prompt_tokens: 0, completion_tokens: 0, thinking_tokens: 0, total_tokens: 0, estimated_cost_usd: 0, model: '', provider: '' }
      const fallbackNotices = []
      let transcribeError = null

      for (let v = 0; v < nResponses; v++) {
        try {
          const result = await transcribe({ ...buildParams(r.root), n_responses: 1 })
          if (result.success) {
            accumulatedOutputs.push(...result.outputs)
            if (result.fallback_used && result.fallback_info) {
              fallbackNotices.push(result.fallback_info)
            }
            const t = result.tokens_usage
            if (t) {
              aggregatedTokens.prompt_tokens += t.prompt_tokens || 0
              aggregatedTokens.completion_tokens += t.completion_tokens || 0
              aggregatedTokens.thinking_tokens += t.thinking_tokens || 0
              aggregatedTokens.total_tokens += t.total_tokens || 0
              aggregatedTokens.estimated_cost_usd += t.estimated_cost_usd || 0
              aggregatedTokens.model = t.model || aggregatedTokens.model
              aggregatedTokens.provider = t.provider || aggregatedTokens.provider
            }
            setTranscriptionBatch((prev) => prev && ({
              ...prev,
              docProgress: { ...prev.docProgress, [r.root]: { ...prev.docProgress[r.root], transcribeVariant: v + 1 } },
            }))
          } else {
            transcribeError = result.error || 'Transcription failed'
            break
          }
        } catch (e) {
          transcribeError = e.message || 'Request failed'
          break
        }
      }

      if (transcribeError) {
        setTranscriptionBatch((prev) => prev && ({
          ...prev,
          errors: [...prev.errors, { root: r.root, error: transcribeError }],
          docProgress: { ...prev.docProgress, [r.root]: { ...prev.docProgress[r.root], error: transcribeError } },
        }))
      } else {
        setTranscriptionResults(accumulatedOutputs, aggregatedTokens, { outputs: accumulatedOutputs, tokens_usage: aggregatedTokens }, fallbackNotices)
        setActiveRootOnly(r.root)
        setTranscriptionBatch((prev) => prev && ({
          ...prev,
          docProgress: { ...prev.docProgress, [r.root]: { ...prev.docProgress[r.root], transcribeDone: true, tokensUsage: aggregatedTokens } },
        }))

        if (nerEnabledNow) {
          setTranscriptionBatch((prev) => prev && ({ ...prev, nerRunning: true }))
          let nerTokensUsage = null
          try {
            const nerData = await runNer({
              root: r.root,
              model: selectedModel,
              provider: selectedProvider,
              gemini_api_key: geminiApiKey,
              openai_api_key: openaiApiKey,
              anthropic_api_key: anthropicApiKey,
              source_indices: accumulatedOutputs.map((_, i) => i),
              entity_types: nerEntityTypes,
            })
            if (nerData.success) {
              setNerResult(nerData.entity_bundle)
              nerTokensUsage = nerData.tokens_usage ?? null
            } else {
              setNerError(nerData.error || 'NER failed')
            }
          } catch (nerErr) {
            setNerError(nerErr.message || 'NER request failed')
          }
          setTranscriptionBatch((prev) => prev && ({
            ...prev,
            nerRunning: false,
            docProgress: { ...prev.docProgress, [r.root]: { ...prev.docProgress[r.root], nerDone: true, nerTokensUsage } },
          }))
        }
      }

      if (autoSummarize) {
        setTranscriptionBatch((prev) => prev && ({ ...prev, summarizeRunning: true }))
        try {
          const sumResult = await summarize({
            root: r.root,
            model: selectedModel || DEFAULT_MODELS[selectedProvider]?.[0] || '',
            provider: selectedProvider,
            gemini_api_key: geminiApiKey,
            openai_api_key: openaiApiKey,
            anthropic_api_key: anthropicApiKey,
            source_indices: [],
            profile_name: activeProfile,
          })
          if (sumResult.success) {
            setSummaryResult(sumResult.summary)
            setTranscriptionBatch((prev) => prev && ({
              ...prev, summarizeRunning: false, summarizeDone: true, summarizeTokens: sumResult.tokens_used,
            }))
          } else {
            setTranscriptionBatch((prev) => prev && ({
              ...prev, summarizeRunning: false, summarizeError: sumResult.error || 'Summarization failed',
            }))
          }
        } catch (e) {
          setTranscriptionBatch((prev) => prev && ({
            ...prev, summarizeRunning: false, summarizeError: e.message || 'Summarization failed',
          }))
        }
      }

      setTranscriptionBatch((prev) => prev && ({ ...prev, completed: prev.completed + 1 }))
    }

    setTranscriptionBatch((prev) => prev && ({ ...prev, currentRoot: null, endTime: Date.now() }))
    queryClient.invalidateQueries({ queryKey: ['roots'] })

    if (autoHarmonize) {
      const lastRoot = targets[targets.length - 1]?.root
      if (lastRoot) {
        setTranscriptionBatch((prev) => prev && ({ ...prev, harmonizeRunning: true }))
        try {
          const harmonizeParams = {
            root: lastRoot,
            model: selectedModel || DEFAULT_MODELS[selectedProvider]?.[0] || '',
            provider: selectedProvider,
            openai_api_key: openaiApiKey,
            gemini_api_key: geminiApiKey,
            anthropic_api_key: anthropicApiKey,
            source_indices: [],
            profile_name: activeProfile,
          }
          const currentNerResult = useAppStore.getState().nerResult
          if (nerEnabledNow && currentNerResult) {
            harmonizeParams.ner_entity_bundle = currentNerResult
          }
          const harmResult = await harmonize(harmonizeParams)
          if (harmResult.success) {
            setHarmonizationResult(harmResult)
            setTranscriptionBatch((prev) => prev && ({
              ...prev, harmonizeRunning: false, harmonizeDone: true, harmonizeTokens: harmResult.tokens_used,
            }))
          } else {
            setTranscriptionBatch((prev) => prev && ({
              ...prev, harmonizeRunning: false, harmonizeError: harmResult.error || 'Harmonization failed',
            }))
          }
        } catch (e) {
          setTranscriptionBatch((prev) => prev && ({
            ...prev, harmonizeRunning: false, harmonizeError: e.message || 'Harmonization failed',
          }))
        }
      }
    }
  }

  const toggleRoot = (root) => {
    setSelectedRoots((prev) => {
      const next = new Set(prev)
      if (next.has(root)) next.delete(root)
      else next.add(root)
      return next
    })
  }

  const selectAll = () => setSelectedRoots(new Set((roots || []).map((r) => r.root)))
  const selectNone = () => setSelectedRoots(new Set())

  const canTranscribe = selectedRoots.size > 0 && !!apiKey && !batchRunning

  return (
    <TwoColumn>
      <div>
        <div className="section-title" style={{ marginBottom: 'var(--space-3)' }}>Settings</div>

        <ProfileSelector />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', alignItems: 'start' }}>
          <div>
            <NumberStepper
              label="Transcriptions Per Document"
              value={nResponses}
              min={1}
              max={10}
              onChange={setNResponses}
            />

            <div style={{ marginTop: 'var(--space-4)' }}>
              <label style={{ color: 'var(--color-text-muted)' }}>After Transcription</label>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={autoSummarize}
                    onChange={(e) => setAutoSummarize(e.target.checked)}
                  />
                  Summarize
                  <TooltipIcon title="Generates a document summary noting uncertain named entities" />
                </label>

                <label
                  className="checkbox-label"
                  style={{ opacity: nResponses < 2 ? 0.45 : 1, pointerEvents: nResponses < 2 ? 'none' : 'auto' }}
                >
                  <input
                    type="checkbox"
                    checked={autoHarmonize}
                    onChange={(e) => setAutoHarmonize(e.target.checked)}
                    disabled={nResponses < 2}
                  />
                  Harmonize
                  <TooltipIcon title="Combines all transcriptions into a single consensus using the selected model" />
                </label>

                <div>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={nerEnabled}
                      onChange={(e) => setNerEnabled(e.target.checked)}
                    />
                    Find Named Entities
                    <TooltipIcon title="Run Named Entity Recognition after transcription completes" />
                  </label>

                  <NerEntityTypeEditor types={nerEntityTypes} onChange={setNerEntityTypes} disabled={!nerEnabled} />
                </div>
              </div>
            </div>
          </div>

          <TextArea
            label="Domain Knowledge (optional)"
            value={domainKnowledge}
            onChange={(e) => setDomainKnowledge(e.target.value)}
            placeholder="Add any domain-specific context to improve transcription accuracy…"
            style={{ height: 200 }}
          />
        </div>
      </div>

      <div>
        <DocumentSection
          roots={roots}
          selectedRoots={selectedRoots}
          onToggle={toggleRoot}
          onSelectAll={selectAll}
          onSelectNone={selectNone}
        />

        <div style={{ marginTop: 'var(--space-4)', display: 'flex', alignItems: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Button
            variant="primary"
            size="lg"
            onClick={handleTranscribe}
            disabled={!canTranscribe}
          >
            {batchRunning ? (
              <><InlineSpinner /> Transcribing…</>
            ) : (
              `⚡ Transcribe (${selectedRoots.size})`
            )}
          </Button>

          {!apiKey && (
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
              Enter an API key to enable transcription
            </span>
          )}
        </div>

        {/* Transcription progress — persists until explicitly dismissed */}
        {transcriptionBatch && (
          <BatchProgressPanel batch={transcriptionBatch} />
        )}
      </div>
    </TwoColumn>
  )
}

// ── Icon + label sub-row for transcription/NER phase lines ───────────────────

function SubRow({ icon, iconColor, label, muted }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--font-size-sm)' }}>
      <span style={{ width: 14, textAlign: 'center', flexShrink: 0, color: iconColor || 'var(--color-text-muted)' }}>{icon}</span>
      <span style={{ color: muted ? 'var(--color-text-muted)' : 'var(--color-text)' }}>{label}</span>
    </div>
  )
}

// ── Unified batch progress panel (running + done; persists until dismissed) ───

function BatchProgressPanel({ batch }) {
  const {
    targets = [], total, completed, currentRoot, nerRunning, startTime, endTime, docProgress = {},
    autoHarmonize: batchAutoHarmonize, harmonizeRunning, harmonizeDone, harmonizeTokens, harmonizeError,
    autoSummarize: batchAutoSummarize, summarizeRunning, summarizeDone, summarizeTokens, summarizeError,
  } = batch
  const isDone = currentRoot === null && !harmonizeRunning
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0

  // Elapsed timer — stops ticking once fully done (including harmonize)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (isDone) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [isDone])
  const elapsedSec = Math.floor(((isDone ? endTime : now) - startTime) / 1000)
  const elapsedStr = elapsedSec >= 60 ? `${Math.floor(elapsedSec / 60)}m ${elapsedSec % 60}s` : `${elapsedSec}s`

  const headerLabel = currentRoot === null && harmonizeRunning
    ? `Harmonizing…  ·  Elapsed: ${elapsedStr}`
    : isDone
      ? `✓ Complete: ${total} document${total !== 1 ? 's' : ''}  ·  Elapsed: ${elapsedStr}`
      : `Processing ${completed + 1} of ${total}  ·  Elapsed: ${elapsedStr}`

  const harmTok = harmonizeTokens
  const harmTokLabel = harmTok && (harmTok.prompt_tokens || harmTok.completion_tokens)
    ? '  ·  ' + [
        `${(harmTok.prompt_tokens || 0).toLocaleString()} in`,
        `${(harmTok.completion_tokens || 0).toLocaleString()} out`,
        ...(harmTok.estimated_cost_usd > 0 ? [`$${harmTok.estimated_cost_usd.toFixed(3)}`] : []),
      ].join(' · ')
    : ''

  const sumTok = summarizeTokens
  const sumTokLabel = sumTok && (sumTok.prompt_tokens || sumTok.completion_tokens)
    ? '  ·  ' + [
        `${(sumTok.prompt_tokens || 0).toLocaleString()} in`,
        `${(sumTok.completion_tokens || 0).toLocaleString()} out`,
      ].join(' · ')
    : ''

  // Token totals across all completed docs (transcription + NER + summarize + harmonize)
  const totalTokens = targets.reduce((sum, root) => {
    const dp = docProgress[root] || {}
    return sum + (dp.tokensUsage?.total_tokens || 0) + (dp.nerTokensUsage?.total?.total_tokens || 0)
  }, 0) + (harmonizeTokens?.total_tokens || 0) + (summarizeTokens?.total_tokens || 0)
  const totalCost = targets.reduce((sum, root) => sum + (docProgress[root]?.tokensUsage?.estimated_cost_usd || 0), 0)
    + (harmonizeTokens?.estimated_cost_usd || 0)

  return (
    <div style={{
      marginTop: 'var(--space-4)',
      padding: 'var(--space-4)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius)',
      background: 'var(--color-surface)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--space-2)', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
        <span style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>
          {headerLabel}
        </span>
      </div>

      {/* Doc-level progress bar */}
      <div style={{ height: 6, borderRadius: 3, background: 'var(--color-border)', marginBottom: 'var(--space-4)', overflow: 'hidden' }}>
        <div style={{ height: '100%', borderRadius: 2, background: 'var(--color-primary)', width: `${pct}%`, transition: 'width 0.4s ease' }} />
      </div>

      {/* Per-doc rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {targets.map((root, idx) => {
          const isLast = idx === targets.length - 1
          const dp = docProgress[root] || {}
          const hasError = !!dp.error
          const isDoneDoc = !hasError && dp.transcribeDone && (!dp.nerEnabled || dp.nerDone)
          const isQueued = !isDoneDoc && !hasError && root !== currentRoot

          const tok = dp.tokensUsage
          const tokLabel = tok && (tok.prompt_tokens || tok.completion_tokens)
            ? '  ·  ' + [
                `${(tok.prompt_tokens || 0).toLocaleString()} in`,
                `${(tok.completion_tokens || 0).toLocaleString()} out`,
                ...(tok.thinking_tokens > 0 ? [`${tok.thinking_tokens.toLocaleString()} think`] : []),
                ...(tok.estimated_cost_usd > 0 ? [`$${tok.estimated_cost_usd.toFixed(3)}`] : []),
              ].join(' · ')
            : ''

          const successColor = 'var(--color-success, #22c55e)'
          const docIcon = hasError ? '✗' : isDoneDoc ? '✓' : root === currentRoot ? <InlineSpinner /> : '○'
          const docIconColor = hasError ? 'var(--color-error, #ef4444)' : isDoneDoc ? successColor : 'var(--color-text-muted)'

          const tActive = root === currentRoot && !dp.transcribeDone
          const tIcon = dp.transcribeDone ? '✓' : tActive ? <InlineSpinner /> : '○'
          const tIconColor = dp.transcribeDone ? successColor : 'var(--color-text-muted)'
          const tLabel = dp.transcribeDone
            ? `Transcribed  ·  ${dp.transcribeVariant} / ${dp.transcribeTotal}${tokLabel}`
            : isQueued
              ? 'Transcription (queued)'
              : `Transcribing  ${dp.transcribeVariant} / ${dp.transcribeTotal}`

          const nActive = nerRunning && root === currentRoot
          const nIcon = dp.nerDone ? '✓' : nActive ? <InlineSpinner /> : '○'
          const nIconColor = dp.nerDone ? successColor : 'var(--color-text-muted)'
          const nerTok = dp.nerTokensUsage?.total
          const nerTokLabel = nerTok
            ? '  ·  ' + [
                `${nerTok.input_tokens.toLocaleString()} in`,
                `${nerTok.output_tokens.toLocaleString()} out`,
                ...(nerTok.thinking_tokens > 0 ? [`${nerTok.thinking_tokens.toLocaleString()} think`] : []),
              ].join(' · ')
            : ''

          return (
            <div key={root}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 4, fontSize: 'var(--font-size-sm)' }}>
                <span style={{ width: 16, textAlign: 'center', flexShrink: 0, color: docIconColor }}>{docIcon}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: isQueued ? 'var(--color-text-muted)' : 'var(--color-text)' }}>{root}</span>
              </div>

              <div style={{ marginLeft: 24, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {hasError ? (
                  <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-error, #ef4444)' }}>{dp.error}</span>
                ) : (
                  <>
                    <SubRow icon={tIcon} iconColor={tIconColor} label={tLabel} muted={isQueued} />
                    {dp.nerEnabled && (
                      <SubRow icon={nIcon} iconColor={nIconColor} label={dp.nerDone ? `Named Entities found${nerTokLabel}` : nActive ? 'Finding Named Entities' : 'Finding Named Entities (queued)'} muted={!dp.transcribeDone} />
                    )}
                    {batchAutoSummarize && (() => {
                      const sc = 'var(--color-success, #22c55e)'
                      const sIsActive = summarizeRunning && root === currentRoot
                      const sIcon = summarizeError && root === currentRoot ? '✗' : summarizeDone ? '✓' : sIsActive ? <InlineSpinner /> : '○'
                      const sColor = summarizeError && root === currentRoot ? 'var(--color-error, #ef4444)' : summarizeDone ? sc : 'var(--color-text-muted)'
                      const sLabel = summarizeError && root === currentRoot
                        ? `Summarization failed: ${summarizeError}`
                        : summarizeDone ? `Summarized${sumTokLabel}`
                        : sIsActive ? 'Summarizing…'
                        : 'Summarize (queued)'
                      return <SubRow icon={sIcon} iconColor={sColor} label={sLabel} muted={!sIsActive && !summarizeDone && !(summarizeError && root === currentRoot)} />
                    })()}
                    {isLast && batchAutoHarmonize && (() => {
                      const sc = 'var(--color-success, #22c55e)'
                      const hIcon = harmonizeError ? '✗' : harmonizeDone ? '✓' : harmonizeRunning ? <InlineSpinner /> : '○'
                      const hColor = harmonizeError ? 'var(--color-error, #ef4444)' : harmonizeDone ? sc : 'var(--color-text-muted)'
                      const hLabel = harmonizeError
                        ? `Harmonization failed: ${harmonizeError}`
                        : harmonizeDone ? `Harmonized${harmTokLabel}`
                        : harmonizeRunning ? 'Harmonizing…'
                        : 'Harmonize (queued)'
                      return <SubRow icon={hIcon} iconColor={hColor} label={hLabel} muted={!harmonizeRunning && !harmonizeDone && !harmonizeError} />
                    })()}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Token footer */}
      {totalTokens > 0 && (
        <div style={{ marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--color-border)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
          {isDone ? 'Total:' : `${completed} of ${total} done  ·  Total so far:`}{' '}
          <strong style={{ color: 'var(--color-text)' }}>{totalTokens.toLocaleString()} tokens</strong>
          {totalCost > 0 && <span>  ·  ${totalCost.toFixed(3)}</span>}
        </div>
      )}
    </div>
  )
}
