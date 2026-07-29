import { useEffect, useState } from 'react'
import DOMPurify from 'dompurify'
import { useAppStore } from '../../store/appStore.js'
import { useImage } from '../../hooks/useImage.js'
import { useColorize } from '../../hooks/useColorize.js'
import { useRoots } from '../../hooks/useRoots.js'
import { useJsonData } from '../../hooks/useJsonData.js'
import { Button } from '../shared/Button.jsx'
import { Spinner } from '../shared/Spinner.jsx'
import { Alert } from '../shared/Alert.jsx'
import { FallbackNotice } from '../shared/FallbackNotice.jsx'
import { Expander } from '../shared/Expander.jsx'

const COLOR_MODES = ['Word-level', 'Char-level', 'Named Entities']

const labelStyle = { fontSize: 'var(--font-size-sm)', fontWeight: 600, margin: 0, marginBottom: 4 }

function AnalysisControls({ colorReason }) {
  const outputs = useAppStore((s) => s.outputs)
  const selIdx = useAppStore((s) => s.selIdx)
  const colorMode = useAppStore((s) => s.colorMode)
  const textFontSize = useAppStore((s) => s.textFontSize)
  const selHarmonized = useAppStore((s) => s.selHarmonized)
  const harmonizationResult = useAppStore((s) => s.harmonizationResult)
  const nerResult = useAppStore((s) => s.nerResult)
  const activeRoot = useAppStore((s) => s.activeRoot)
  const setActiveRoot = useAppStore((s) => s.setActiveRoot)
  const setSelIdx = useAppStore((s) => s.setSelIdx)
  const setColorMode = useAppStore((s) => s.setColorMode)
  const setTextFontSize = useAppStore((s) => s.setTextFontSize)
  const setSelHarmonized = useAppStore((s) => s.setSelHarmonized)
  const { data: roots } = useRoots()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>

      {/* Document selector */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <label style={labelStyle}>Document</label>
        <select
          className="form-control"
          value={activeRoot}
          onChange={(e) => setActiveRoot(e.target.value)}
        >
          {roots?.map((r) => (
            <option key={r.root} value={r.root}>{r.root}</option>
          ))}
        </select>
      </div>

      {/* Transcription selector */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <label style={labelStyle}>Transcription</label>
        <select
          className="form-control"
          value={selHarmonized ? 'harmonized' : String(selIdx)}
          onChange={(e) => {
            if (e.target.value === 'harmonized') setSelHarmonized(true)
            else { setSelHarmonized(false); setSelIdx(Number(e.target.value)) }
          }}
        >
          {outputs.map((_, i) => <option key={i} value={String(i)}>Transcription {i + 1}</option>)}
          {harmonizationResult && <option value="harmonized">Harmonized</option>}
        </select>
      </div>

      {/* Color mode */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <label style={labelStyle}>Color Mode</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {COLOR_MODES.map((mode) => (
            <button
              key={mode}
              className={`btn btn-secondary${colorMode === mode ? ' active' : ''}`}
              style={{ width: '100%', textAlign: 'left' }}
              onClick={() => setColorMode(mode)}
              disabled={mode === 'Named Entities' && !nerResult}
              title={mode === 'Named Entities' && !nerResult ? 'Run NER first' : ''}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Font size */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <label style={labelStyle}>Font Size</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Button variant="ghost" size="sm" onClick={() => setTextFontSize(Math.max(60, textFontSize - 10))}>A−</Button>
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', minWidth: 36, textAlign: 'center' }}>{textFontSize}%</span>
          <Button variant="ghost" size="sm" onClick={() => setTextFontSize(Math.min(200, textFontSize + 10))}>A+</Button>
          <Button variant="ghost" size="sm" onClick={() => setTextFontSize(100)} title="Reset font size">↺</Button>
        </div>
      </div>

      {/* Single-transcription warning */}
      {colorReason && <Alert type="warning">{colorReason}</Alert>}
      {!nerResult && <Alert type="warning">NER has not been run — Named Entity highlighting is unavailable.</Alert>}
    </div>
  )
}

function ImagePanel({ root }) {
  const { data, isLoading } = useImage(root)

  return (
    <div className="image-preview">
      {isLoading ? (
        <Spinner label="Loading image…" />
      ) : data?.image_b64 ? (
        <img
          src={`data:${data.mime || 'image/png'};base64,${data.image_b64}`}
          alt={root}
          style={{ maxHeight: 'calc(100vh - var(--header-height) - var(--tab-bar-height) - 2 * var(--space-3) - var(--space-6))', maxWidth: '100%', width: 'auto', display: 'block' }}
        />
      ) : (
        <div className="image-preview-empty">No image loaded</div>
      )}
    </div>
  )
}

function ColorizedOutput({ html, fontSize, isLoading }) {
  const clean = DOMPurify.sanitize(html || '', {
    ALLOWED_TAGS: ['span', 'div', 'p', 'br', 'mark'],
    ALLOWED_ATTR: ['style', 'class', 'title'],
  })

  if (isLoading) return <Spinner label="Computing colorization…" />

  const containerStyle = {
    fontSize: `${fontSize}%`,
    lineHeight: 1.7,
    padding: 'var(--space-3)',
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    flex: 1,
    overflowY: 'auto',
    minHeight: 0,
    maxHeight: 'calc(100vh - var(--header-height) - var(--tab-bar-height) - 2 * var(--space-3) - var(--space-6))',
    wordBreak: 'break-word',
    whiteSpace: 'pre-wrap',
    fontFamily: 'var(--font-mono)',
  }

  if (!clean) {
    return (
      <div className="scroll-panel" style={{ ...containerStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)' }}>
        No transcription yet
      </div>
    )
  }

  return (
    <div
      className="scroll-panel"
      style={containerStyle}
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}

function EditPanel({ text, onSave, onCancel }) {
  const [value, setValue] = useState(text)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <textarea
        className="form-control scroll-panel"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{ flex: 1, overflowY: 'auto', resize: 'none', minHeight: 0, fontFamily: 'var(--font-mono)', fontSize: 14 }}
      />
      <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexShrink: 0 }}>
        <Button variant="primary" size="sm" onClick={() => onSave(value)}>💾 Save</Button>
        <Button variant="secondary" size="sm" onClick={onCancel}>✕ Cancel</Button>
      </div>
    </div>
  )
}

function NerReport({ nerResult }) {
  if (!nerResult) return null
  const entities = nerResult.entities || []
  if (entities.length === 0) return null

  return (
    <div className="section" style={{ marginTop: 'var(--space-4)' }}>
      <div className="section-title">Named Entities ({entities.length})</div>
      {entities.map((entity, i) => (
        <Expander
          key={entity.entity_id || i}
          title={`${entity.canonical || '(unresolved)'} — ${entity.type || ''}`}
        >
          <div style={{ fontSize: 'var(--font-size-sm)', display: 'grid', gap: 'var(--space-2)' }}>
            {entity.about && <p style={{ margin: 0 }}><strong>About:</strong> {entity.about}</p>}
            {entity.role_in_document && <p style={{ margin: 0 }}><strong>Role:</strong> {entity.role_in_document}</p>}
            {entity.observed_variants?.length > 0 && (
              <p style={{ margin: 0 }}><strong>Variants:</strong> {entity.observed_variants.join(', ')}</p>
            )}
            {entity.disambiguation && <p style={{ margin: 0 }}><strong>Disambiguation:</strong> {entity.disambiguation}</p>}
            {entity.resolution_notes && <p style={{ margin: 0 }}><strong>Resolution notes:</strong> {entity.resolution_notes}</p>}
            {entity.confidence && <p style={{ margin: 0 }}><strong>Confidence:</strong> {entity.confidence}</p>}
          </div>
        </Expander>
      ))}
    </div>
  )
}

export function AnalysisTab() {
  const activeRoot = useAppStore((s) => s.activeRoot)
  const outputs = useAppStore((s) => s.outputs)
  const transcriptionFallbackNotices = useAppStore((s) => s.transcriptionFallbackNotices)
  const selIdx = useAppStore((s) => s.selIdx)
  const textFontSize = useAppStore((s) => s.textFontSize)
  const analysisEditMode = useAppStore((s) => s.analysisEditMode)
  const analysisEditText = useAppStore((s) => s.analysisEditText)
  const nerResult = useAppStore((s) => s.nerResult)
  const setAnalysisEditMode = useAppStore((s) => s.setAnalysisEditMode)
  const updateOutputText = useAppStore((s) => s.updateOutputText)
  const setTranscriptionResults = useAppStore((s) => s.setTranscriptionResults)
  const setNerResult = useAppStore((s) => s.setNerResult)

  const { colorizedHtml, colorReason, isLoading: colorLoading } = useColorize()
  const { data: jsonData } = useJsonData(activeRoot)

  useEffect(() => {
    if (!jsonData || outputs.length > 0) return
    const runs = jsonData.runs || []
    if (runs.length === 0) return
    const lastRun = runs[runs.length - 1]
    const texts = (lastRun.outputs || []).map((o) => (typeof o === 'string' ? o : o.text || ''))
    if (texts.length === 0) return
    setTranscriptionResults(
      texts,
      {
        prompt_tokens: lastRun.tokens_in || 0,
        completion_tokens: lastRun.tokens_out || 0,
        estimated_cost_usd: lastRun.estimated_cost_usd ?? null,
        model: lastRun.model || '',
        provider: lastRun.provider || '',
      },
      null,
    )
  }, [jsonData, outputs.length, setTranscriptionResults])

  useEffect(() => {
    if (!jsonData || nerResult) return
    const nerResults = jsonData.ner_results || []
    if (nerResults.length === 0) return
    const lastNer = nerResults[nerResults.length - 1]
    if (lastNer.entity_bundle) {
      setNerResult(lastNer.entity_bundle)
    }
  }, [jsonData, nerResult, setNerResult])

  const currentText = typeof outputs[selIdx] === 'string'
    ? outputs[selIdx]
    : outputs[selIdx]?.text || ''

  return (
    <div>
      {!activeRoot && (
        <Alert type="info">📤 Upload a document and transcribe it first.</Alert>
      )}
      {activeRoot && (!outputs || outputs.length === 0) && (
        <Alert type="info">📝 Transcribe the document first in the Transcription tab.</Alert>
      )}
      {transcriptionFallbackNotices.map((info, i) => (
        <FallbackNotice key={i} fallbackInfo={info} />
      ))}

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 180px',
        gap: 'var(--space-4)',
        alignItems: 'stretch',
      }}>

        {/* Image column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Image</div>
          <ImagePanel root={activeRoot} />
        </div>

        {/* Transcription column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', minHeight: 0, overflow: 'hidden' }}>
          <div style={{ position: 'relative' }}>
            <div className="section-title" style={{ marginBottom: 0 }}>Transcription</div>
            {!analysisEditMode && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setAnalysisEditMode(true, currentText)}
                style={{ position: 'absolute', top: 0, right: 0 }}
              >
                ✏️ Edit
              </Button>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            {analysisEditMode ? (
              <EditPanel
                text={analysisEditText}
                onSave={(text) => updateOutputText(selIdx, text)}
                onCancel={() => setAnalysisEditMode(false)}
              />
            ) : (
              <ColorizedOutput
                html={colorizedHtml}
                fontSize={textFontSize}
                isLoading={colorLoading}
              />
            )}
          </div>
        </div>

        {/* Settings column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Settings</div>
          <AnalysisControls colorReason={colorReason} />
        </div>

      </div>

      <NerReport nerResult={nerResult} />
    </div>
  )
}
