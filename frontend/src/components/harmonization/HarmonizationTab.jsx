import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { harmonize } from '../../api/harmonization.js'
import { useAppStore } from '../../store/appStore.js'
import { Button } from '../shared/Button.jsx'
import { PasswordInput } from '../shared/PasswordInput.jsx'
import { Alert } from '../shared/Alert.jsx'
import { FallbackNotice } from '../shared/FallbackNotice.jsx'
import { Expander } from '../shared/Expander.jsx'
import { InlineSpinner } from '../shared/Spinner.jsx'

const PROVIDERS = ['Gemini', 'OpenAI', 'Anthropic']

const DEFAULT_MODELS = {
  Gemini: ['gemini-3.1-pro-preview', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash'],
  OpenAI: ['gpt-5.5', 'gpt-5', 'gpt-4o', 'gpt-4o-mini'],
  Anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5'],
}

function TranscriptionCheckboxes({ outputs, selected, onChange }) {
  return (
    <div className="section">
      <div className="section-title">Select Transcriptions to Harmonize</div>
      {outputs.length === 0 ? (
        <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)', margin: 0 }}>
          No transcriptions yet — run transcriptions in the Transcription tab.
        </p>
      ) : (
        outputs.map((out, i) => {
          const text = typeof out === 'string' ? out : out?.text || ''
          const checked = selected.includes(i)
          return (
            <div key={i} style={{ marginBottom: 'var(--space-2)' }}>
              <label className="checkbox-label" style={{ marginBottom: 4 }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    if (checked) onChange(selected.filter((x) => x !== i))
                    else onChange([...selected, i])
                  }}
                />
                Transcription {i + 1} ({text.length} chars)
              </label>
              {checked && (
                <div style={{
                  marginLeft: 24,
                  padding: 'var(--space-2)',
                  background: 'var(--color-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-xs)',
                  fontFamily: 'var(--font-mono)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: 80,
                  overflow: 'hidden',
                }}>
                  {text.slice(0, 300)}{text.length > 300 ? '…' : ''}
                </div>
              )}
            </div>
          )
        })
      )}
      {selected.length >= 2 && (
        <div className="form-hint">{selected.length} transcriptions selected</div>
      )}
    </div>
  )
}

function ComparisonView({ outputs, harmonizationResult, selected }) {
  const [innerTab, setInnerTab] = useState(0)
  const tabs = [
    ...selected.map((i) => `Transcription ${i + 1}`),
    'Harmonized',
  ]

  const getText = (tabIdx) => {
    if (tabIdx < selected.length) {
      const out = outputs[selected[tabIdx]]
      return typeof out === 'string' ? out : out?.text || ''
    }
    return harmonizationResult?.harmonized_text || ''
  }

  return (
    <div>
      <div className="inner-tabs">
        {tabs.map((t, i) => (
          <button
            key={t}
            className={`inner-tab-btn${innerTab === i ? ' active' : ''}`}
            onClick={() => setInnerTab(i)}
          >
            {t}
          </button>
        ))}
      </div>
      <pre style={{
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        fontSize: 'var(--font-size-sm)',
        fontFamily: 'var(--font-mono)',
        background: 'var(--color-secondary)',
        padding: 'var(--space-3)',
        borderRadius: 'var(--radius-md)',
        minHeight: 120,
      }}>
        {getText(innerTab)}
      </pre>
    </div>
  )
}

export function HarmonizationTab() {
  const activeRoot = useAppStore((s) => s.activeRoot)
  const outputs = useAppStore((s) => s.outputs)
  const harmonizationSelected = useAppStore((s) => s.harmonizationSelected)
  const harmonizationResult = useAppStore((s) => s.harmonizationResult)
  const harmonizationProvider = useAppStore((s) => s.harmonizationProvider)
  const harmonizationModel = useAppStore((s) => s.harmonizationModel)
  const harmonizationApiKey = useAppStore((s) => s.harmonizationApiKey)
  const openaiApiKey = useAppStore((s) => s.openaiApiKey)
  const geminiApiKey = useAppStore((s) => s.geminiApiKey)
  const anthropicApiKey = useAppStore((s) => s.anthropicApiKey)
  const activeProfile = useAppStore((s) => s.activeProfile)
  const setHarmonizationSelected = useAppStore((s) => s.setHarmonizationSelected)
  const setHarmonizationProvider = useAppStore((s) => s.setHarmonizationProvider)
  const setHarmonizationModel = useAppStore((s) => s.setHarmonizationModel)
  const setHarmonizationApiKey = useAppStore((s) => s.setHarmonizationApiKey)
  const setHarmonizationResult = useAppStore((s) => s.setHarmonizationResult)
  const clearHarmonizationResult = useAppStore((s) => s.clearHarmonizationResult)
  const setError = useAppStore((s) => s.setError)

  const effectiveApiKey = harmonizationApiKey || (harmonizationProvider === 'OpenAI' ? openaiApiKey : harmonizationProvider === 'Anthropic' ? anthropicApiKey : geminiApiKey)
  const modelOptions = DEFAULT_MODELS[harmonizationProvider] || []
  const currentModel = harmonizationModel || modelOptions[0] || ''

  const [copied, setCopied] = useState(false)

  const harmonizeMutation = useMutation({
    mutationFn: harmonize,
    onSuccess: (data) => {
      if (data.success || data.harmonized_text) {
        setHarmonizationResult(data)
      } else {
        setError(data.error || 'Harmonization failed', 'Harmonization')
      }
    },
    onError: (err) => setError(err.message, 'Harmonization'),
  })

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(harmonizationResult?.harmonized_text || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Could not copy to clipboard. Please copy manually.', 'Clipboard')
    }
  }

  const saveAsFile = () => {
    const text = harmonizationResult?.harmonized_text || ''
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement('a'), {
      href: url,
      download: `${activeRoot}_harmonized.txt`,
    })
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      {!activeRoot && <Alert type="info">📤 Upload a document first.</Alert>}
      {activeRoot && (!outputs || outputs.length < 2) && (
        <Alert type="warning">
          ⚠️ At least 2 transcriptions are required for harmonization. Currently have {outputs?.length || 0}.
          Go to the Transcription tab and run more transcriptions.
        </Alert>
      )}

      <TranscriptionCheckboxes
        outputs={outputs}
        selected={harmonizationSelected}
        onChange={setHarmonizationSelected}
      />

      <div className="card section">
        <div className="section-title">Harmonization Settings</div>
        <div className="form-group">
          <label>Provider</label>
          <select className="form-control" value={harmonizationProvider} onChange={(e) => setHarmonizationProvider(e.target.value)}>
            {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Model</label>
          <select className="form-control" value={currentModel} onChange={(e) => setHarmonizationModel(e.target.value)}>
            {modelOptions.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <PasswordInput
          label={`${harmonizationProvider} API Key`}
          value={harmonizationApiKey}
          onChange={(e) => setHarmonizationApiKey(e.target.value)}
          placeholder={effectiveApiKey ? '(using key from Transcription tab)' : 'Enter API key…'}
        />
        <Button
          variant="primary"
          size="lg"
          onClick={() => harmonizeMutation.mutate({
            root: activeRoot,
            model: currentModel,
            provider: harmonizationProvider,
            openai_api_key: harmonizationProvider === 'OpenAI' ? effectiveApiKey : '',
            gemini_api_key: harmonizationProvider === 'Gemini' ? effectiveApiKey : '',
            anthropic_api_key: harmonizationProvider === 'Anthropic' ? effectiveApiKey : '',
            source_indices: harmonizationSelected,
            profile_name: activeProfile,
          })}
          disabled={!effectiveApiKey || harmonizeMutation.isPending || harmonizationSelected.length < 2}
        >
          {harmonizeMutation.isPending
            ? <><InlineSpinner /> Harmonizing…</>
            : `🤝 Harmonize ${harmonizationSelected.length} Transcriptions`}
        </Button>
        {harmonizationSelected.length < 2 && (
          <div className="form-hint">Select at least 2 transcriptions above to enable harmonization.</div>
        )}
      </div>

      <div className="section">
        <div className="section-title">Harmonized Result</div>
        {harmonizationResult ? (
          <>
            <div className="metric-strip" style={{ marginBottom: 'var(--space-3)' }}>
              <div className="metric-item">
                <span className="metric-label">Sources</span>
                <span className="metric-value">{harmonizationResult.source_count || harmonizationSelected.length}</span>
              </div>
              {harmonizationResult.model_used && (
                <div className="metric-item">
                  <span className="metric-label">Model</span>
                  <span className="metric-value" style={{ fontSize: 'var(--font-size-sm)' }}>{harmonizationResult.model_used}</span>
                </div>
              )}
              {harmonizationResult.tokens_used?.total_tokens && (
                <div className="metric-item">
                  <span className="metric-label">Tokens</span>
                  <span className="metric-value">{harmonizationResult.tokens_used.total_tokens.toLocaleString()}</span>
                </div>
              )}
            </div>

            <FallbackNotice fallbackInfo={harmonizationResult.fallback_info} />

            <textarea
              className="form-control"
              readOnly
              value={harmonizationResult.harmonized_text || ''}
              style={{ minHeight: 200, fontFamily: 'var(--font-mono)', fontSize: 14, resize: 'vertical' }}
            />

            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
              <Button variant="secondary" size="sm" onClick={copyToClipboard}>
                {copied ? '✅ Copied!' : '📋 Copy'}
              </Button>
              <Button variant="secondary" size="sm" onClick={saveAsFile}>💾 Save as File</Button>
              <Button variant="ghost" size="sm" onClick={clearHarmonizationResult}>🔄 Clear</Button>
            </div>

            <div style={{ marginTop: 'var(--space-3)' }}>
              <Expander title="Compare Transcriptions">
                <ComparisonView
                  outputs={outputs}
                  harmonizationResult={harmonizationResult}
                  selected={harmonizationSelected}
                />
              </Expander>
            </div>
          </>
        ) : (
          <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)', margin: 0 }}>
            Run harmonization to see the consensus result here.
          </p>
        )}
      </div>
    </div>
  )
}
