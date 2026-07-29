import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { exportAll } from '../../api/export.js'
import { generateTts } from '../../api/tts.js'
import { TTS_UI_ENABLED } from '../../featureFlags.js'
import { useAppStore } from '../../store/appStore.js'
import { useProfile } from '../../hooks/useProfiles.js'
import { useRoots } from '../../hooks/useRoots.js'
import { Button } from '../shared/Button.jsx'
import { PasswordInput } from '../shared/PasswordInput.jsx'
import { TextArea } from '../shared/TextArea.jsx'
import { Alert } from '../shared/Alert.jsx'
import { FallbackNotice } from '../shared/FallbackNotice.jsx'
import { InlineSpinner } from '../shared/Spinner.jsx'

const TTS_MODELS = [
  { value: 'tts-1', label: 'tts-1 — Standard quality ($0.015/1k chars)' },
  { value: 'tts-1-hd', label: 'tts-1-hd — HD quality ($0.030/1k chars)' },
]

const TTS_VOICES = [
  { value: 'alloy', label: 'Alloy — Neutral, balanced' },
  { value: 'echo', label: 'Echo — Male, balanced' },
  { value: 'fable', label: 'Fable — British, expressive' },
  { value: 'onyx', label: 'Onyx — Deep, authoritative (default)' },
  { value: 'nova', label: 'Nova — Female, warm' },
  { value: 'shimmer', label: 'Shimmer — Female, soft' },
]

function DownloadButton({ label, format, disabled }) {
  const [downloading, setDownloading] = useState(false)
  const setError = useAppStore((s) => s.setError)

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await exportAll(format)
      const url = URL.createObjectURL(res.data)
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `export.${format}`
      const a = Object.assign(document.createElement('a'), {
        href: url,
        download: filename,
      })
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message, 'Export')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Button variant="secondary" onClick={handleDownload} disabled={downloading || disabled}>
      {downloading ? <><InlineSpinner /> Preparing…</> : label}
    </Button>
  )
}

function AudioPlayer({ audioCacheB64, metadata }) {
  const audioRef = useRef(null)
  const blobUrlRef = useRef(null)

  useEffect(() => {
    if (!audioCacheB64) return
    const bytes = atob(audioCacheB64)
    const arr = new Uint8Array(bytes.length)
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
    const blob = new Blob([arr], { type: 'audio/wav' })
    blobUrlRef.current = URL.createObjectURL(blob)
    if (audioRef.current) audioRef.current.src = blobUrlRef.current
    return () => { if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current) }
  }, [audioCacheB64])

  if (!audioCacheB64) return null

  const downloadAudio = () => {
    const a = Object.assign(document.createElement('a'), {
      href: blobUrlRef.current,
      download: `narration_${metadata?.voice || 'audio'}.wav`,
    })
    a.click()
  }

  return (
    <div className="card" style={{ marginTop: 'var(--space-3)' }}>
      <audio ref={audioRef} controls style={{ width: '100%', marginBottom: 'var(--space-2)' }} />
      {metadata && (
        <div className="metric-strip" style={{ marginBottom: 'var(--space-2)', flexWrap: 'wrap' }}>
          {metadata.voice && <div className="metric-item"><span className="metric-label">Voice</span><span className="metric-value" style={{ fontSize: 'var(--font-size-sm)' }}>{metadata.voice}</span></div>}
          {metadata.model && <div className="metric-item"><span className="metric-label">Model</span><span className="metric-value" style={{ fontSize: 'var(--font-size-sm)' }}>{metadata.model}</span></div>}
          {metadata.generation_time != null && <div className="metric-item"><span className="metric-label">Gen time</span><span className="metric-value" style={{ fontSize: 'var(--font-size-sm)' }}>{metadata.generation_time.toFixed(1)}s</span></div>}
          {metadata.from_cache && <div className="metric-item"><span className="metric-label">Cache</span><span className="metric-value" style={{ fontSize: 'var(--font-size-sm)' }}>✅ Hit</span></div>}
        </div>
      )}
      {metadata?.fallback_used && <FallbackNotice fallbackInfo={metadata.fallback_info} />}
      <Button variant="secondary" size="sm" onClick={downloadAudio}>📥 Download Audio</Button>
    </div>
  )
}

function TtsSection() {
  const harmonizationResult = useAppStore((s) => s.harmonizationResult)
  const verbalize = useAppStore((s) => s.verbalize)
  const openaiApiKey = useAppStore((s) => s.openaiApiKey)
  const setVerbalize = useAppStore((s) => s.setVerbalize)
  const setError = useAppStore((s) => s.setError)
  const activeRoot = useAppStore((s) => s.activeRoot)

  const apiKey = verbalize.openaiApiKey || openaiApiKey
  const text = verbalize.editedTranscript || harmonizationResult?.harmonized_text || ''
  const charCount = text.length
  const MAX_CHARS = 4096
  const costPer1k = verbalize.ttsModel === 'tts-1-hd' ? 0.030 : 0.015
  const estimatedCost = (charCount / 1000) * costPer1k

  useEffect(() => {
    if (harmonizationResult?.harmonized_text && !verbalize.editedTranscript) {
      setVerbalize({ editedTranscript: harmonizationResult.harmonized_text })
    }
  }, [harmonizationResult?.harmonized_text]) // eslint-disable-line react-hooks/exhaustive-deps

  const ttsMutation = useMutation({
    mutationFn: generateTts,
    onSuccess: (data) => {
      if (data.success) {
        setVerbalize({
          audioCacheB64: data.audio_b64,
          audioMetadata: {
            ...data.metadata,
            from_cache: data.from_cache,
            model_used: data.model_used,
            fallback_used: data.fallback_used,
            fallback_info: data.fallback_info,
          },
          generationStatus: 'complete',
          errorMessage: '',
        })
      } else {
        setVerbalize({ generationStatus: 'error', errorMessage: data.error || 'TTS failed' })
        setError(data.error || 'TTS generation failed', 'Text-to-Speech')
      }
    },
    onError: (err) => {
      setVerbalize({ generationStatus: 'error', errorMessage: err.message })
      setError(err.message, 'Text-to-Speech')
    },
  })

  if (!harmonizationResult) {
    return (
      <Alert type="info">
        🎯 Complete harmonization first — the harmonized text will be used as the narration script.
      </Alert>
    )
  }

  return (
    <div>
      <div className="section-title">Text-to-Speech Narration</div>

      <div className="two-col">
        <div>
          <div className="form-group">
            <label>TTS Model</label>
            <select className="form-control" value={verbalize.ttsModel} onChange={(e) => setVerbalize({ ttsModel: e.target.value })}>
              {TTS_MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Voice</label>
            <select className="form-control" value={verbalize.voice} onChange={(e) => setVerbalize({ voice: e.target.value })}>
              {TTS_VOICES.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </div>
          <PasswordInput
            label="OpenAI API Key"
            value={verbalize.openaiApiKey}
            onChange={(e) => setVerbalize({ openaiApiKey: e.target.value })}
            placeholder={openaiApiKey ? '(using key from Transcription tab)' : 'sk-...'}
          />
        </div>

        <div>
          <div className="metric-strip" style={{ marginBottom: 'var(--space-3)' }}>
            <div className="metric-item">
              <span className="metric-label">Characters</span>
              <span className="metric-value" style={{ color: charCount > MAX_CHARS ? 'var(--color-error)' : undefined }}>{charCount.toLocaleString()}</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Est. cost</span>
              <span className="metric-value">${estimatedCost.toFixed(4)}</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Limit</span>
              <span className="metric-value">{MAX_CHARS.toLocaleString()}</span>
            </div>
          </div>
          {charCount > MAX_CHARS && (
            <Alert type="error">⚠️ Text exceeds {MAX_CHARS} character limit. Please shorten it.</Alert>
          )}
        </div>
      </div>

      <TextArea
        label="Narration Script"
        value={text}
        onChange={(e) => setVerbalize({ editedTranscript: e.target.value })}
        showCount
        style={{ minHeight: 160, fontFamily: 'var(--font-mono)', fontSize: 14 }}
      />

      <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
        <Button
          variant="primary"
          size="lg"
          onClick={() => ttsMutation.mutate({
            text,
            model: verbalize.ttsModel,
            voice: verbalize.voice,
            openai_api_key: apiKey,
            use_cache: true,
            original_image_filename: activeRoot,
          })}
          disabled={!apiKey || charCount === 0 || charCount > MAX_CHARS || ttsMutation.isPending}
        >
          {ttsMutation.isPending ? <><InlineSpinner /> Generating…</> : '🎤 Generate Audio'}
        </Button>
      </div>

      {verbalize.audioCacheB64 && (
        <AudioPlayer audioCacheB64={verbalize.audioCacheB64} metadata={verbalize.audioMetadata} />
      )}
    </div>
  )
}

export function ExportTab() {
  const activeProfile = useAppStore((s) => s.activeProfile)

  const { data: profile } = useProfile(activeProfile)
  const verbalizeEnabled = profile?.verbalize_enabled !== false

  const { data: roots } = useRoots()
  const processedCount = (roots || []).filter((r) => r.run_count > 0).length

  return (
    <div>
      {processedCount === 0 && (
        <Alert type="info">📤 Upload and transcribe a document first.</Alert>
      )}

      <div className="section">
        <div className="section-title">Download Transcriptions</div>
        {processedCount > 1 && (
          <p style={{ color: 'var(--color-text-muted)', marginTop: 0 }}>
            {processedCount} documents processed — each download will be a ZIP with one file per document.
          </p>
        )}
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <DownloadButton label="📄 Download JSON" format="json" disabled={processedCount === 0} />
          <DownloadButton label="📝 Download TXT" format="txt" disabled={processedCount === 0} />
          <DownloadButton label="📘 Download DOCX" format="docx" disabled={processedCount === 0} />
        </div>
      </div>

      {TTS_UI_ENABLED && verbalizeEnabled && (
        <div className="card section">
          <TtsSection />
        </div>
      )}
    </div>
  )
}
