import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadFiles } from '../../api/files.js'
import { useRoots } from '../../hooks/useRoots.js'
import { useImage } from '../../hooks/useImage.js'
import { useModelList } from '../../hooks/useModelList.js'
import { useAppStore } from '../../store/appStore.js'
import { Alert } from '../shared/Alert.jsx'
import { Spinner, InlineSpinner } from '../shared/Spinner.jsx'
import { Button } from '../shared/Button.jsx'
import { PasswordInput } from '../shared/PasswordInput.jsx'
import { TwoColumn } from '../shared/TwoColumn.jsx'

const ACCEPTED_TYPES = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'image/heic': ['.heic'],
  'image/heif': ['.heif'],
  'image/tiff': ['.tif', '.tiff'],
  'image/bmp': ['.bmp']
}

const PROVIDERS = ['Gemini', 'OpenAI', 'Anthropic']

const DEFAULT_MODELS = {
  Gemini: ['gemini-3.1-pro-preview', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash'],
  OpenAI: ['gpt-5.5', 'gpt-5', 'gpt-4o', 'gpt-4o-mini'],
  Anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5'],
}

const SUBSECTION_HEADING = {
  fontWeight: 700,
  fontSize: 'var(--font-size-lg)',
  color: 'var(--color-heading)',
  marginBottom: 'var(--space-3)',
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

function ModelSettings() {
  const selectedProvider = useAppStore((s) => s.selectedProvider)
  const selectedModel = useAppStore((s) => s.selectedModel)
  const openaiApiKey = useAppStore((s) => s.openaiApiKey)
  const geminiApiKey = useAppStore((s) => s.geminiApiKey)
  const anthropicApiKey = useAppStore((s) => s.anthropicApiKey)
  const setProvider = useAppStore((s) => s.setProvider)
  const setModel = useAppStore((s) => s.setModel)
  const setOpenaiApiKey = useAppStore((s) => s.setOpenaiApiKey)
  const setGeminiApiKey = useAppStore((s) => s.setGeminiApiKey)
  const setAnthropicApiKey = useAppStore((s) => s.setAnthropicApiKey)

  const apiKey = selectedProvider === 'OpenAI' ? openaiApiKey : selectedProvider === 'Anthropic' ? anthropicApiKey : geminiApiKey
  const { data: modelData, isLoading: modelsLoading, isSuccess, refetch } = useModelList(selectedProvider, apiKey)

  const verified = !!apiKey && isSuccess && !!modelData?.models?.length
  const modelOptions = verified ? modelData.models : []
  const currentModel = selectedModel || modelOptions[0] || ''

  const handleKeyVerify = (e) => { if (e.key === 'Enter' && apiKey) refetch() }

  return (
    <div>
      <div style={SUBSECTION_HEADING}>Model & API</div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
        <div>
          <label>
            Provider
            <TooltipIcon title="AI provider to use for transcription" />
          </label>
          <select className="form-control" value={selectedProvider} onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <label style={{ margin: 0 }}>
              Model
              <TooltipIcon title="Language model to use for transcription" />
            </label>
            <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={!apiKey}>
              {modelsLoading ? <InlineSpinner /> : '🔄'} Refresh
            </Button>
          </div>
          <select
            className="form-control"
            value={verified ? currentModel : ''}
            onChange={(e) => setModel(e.target.value)}
            disabled={!verified || modelsLoading}
          >
            {!verified
              ? <option value="">{!apiKey ? 'Enter API key to unlock' : modelsLoading ? 'Verifying…' : 'Verification failed — press Enter to retry'}</option>
              : modelOptions.map((m) => <option key={m} value={m}>{m}</option>)
            }
          </select>
        </div>
      </div>

      {selectedProvider === 'OpenAI' ? (
        <PasswordInput
          label="OpenAI API Key"
          value={openaiApiKey}
          onChange={(e) => setOpenaiApiKey(e.target.value)}
          onKeyDown={handleKeyVerify}
          placeholder="sk-..."
        />
      ) : selectedProvider === 'Anthropic' ? (
        <PasswordInput
          label="Anthropic API Key"
          value={anthropicApiKey}
          onChange={(e) => setAnthropicApiKey(e.target.value)}
          onKeyDown={handleKeyVerify}
          placeholder="sk-ant-..."
        />
      ) : (
        <PasswordInput
          label="Gemini API Key"
          value={geminiApiKey}
          onChange={(e) => setGeminiApiKey(e.target.value)}
          onKeyDown={handleKeyVerify}
          placeholder="AI..."
        />
      )}

    </div>
  )
}

function FileDropzone({ onUpload, uploading }) {
  const onDrop = useCallback((files) => {
    if (files.length > 0) onUpload(files)
  }, [onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple: true,
  })

  const style = {
    border: `2px dashed ${isDragActive ? 'var(--color-primary)' : 'var(--color-border)'}`,
    borderRadius: 'var(--radius-md)',
    padding: 'var(--space-6)',
    textAlign: 'center',
    background: isDragActive ? 'var(--color-primary-light)' : 'var(--color-surface)',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background 0.15s',
  }

  return (
    <div {...getRootProps()} style={style}>
      <input {...getInputProps()} />
      {uploading ? (
        <Spinner label="Uploading files…" />
      ) : (
        <>
          <div style={{ fontSize: 40, marginBottom: 'var(--space-2)' }}>📂</div>
          <p style={{ margin: 0, fontWeight: 600 }}>
            {isDragActive ? 'Drop files here' : 'Drag & drop files, or click to browse'}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
            Supported: {Object.values(ACCEPTED_TYPES).flat().map(ext => ext.slice(1).toUpperCase()).join(', ')}
          </p>
        </>
      )}
    </div>
  )
}

function UploadSummary({ result }) {
  if (!result) return null
  const { roots = [], errors = [] } = result
  return (
    <div style={{ marginTop: 'var(--space-3)' }}>
      {roots.length > 0 && (
        <Alert type="success">
          ✅ {roots.length} file{roots.length !== 1 ? 's' : ''} uploaded successfully
        </Alert>
      )}
      {errors.length > 0 && (
        <details className="expander">
          <summary>⚠️ {errors.length} file{errors.length !== 1 ? 's' : ''} skipped</summary>
          <div className="expander-content">
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {errors.map((e, i) => <li key={i} style={{ fontSize: 'var(--font-size-sm)' }}>{e}</li>)}
            </ul>
          </div>
        </details>
      )}
    </div>
  )
}

function ThumbnailCard({ root, runCount, onView }) {
  const { data, isLoading } = useImage(root)

  return (
    <div className="thumbnail-card" onClick={() => onView(root)}>
      <div className="thumbnail-card__img-wrap">
        {isLoading ? (
          <div className="thumbnail-card__skeleton" />
        ) : data?.image_b64 ? (
          <img
            src={`data:${data.mime || 'image/png'};base64,${data.image_b64}`}
            alt={root}
          />
        ) : (
          <span style={{ fontSize: 32, opacity: 0.4 }}>📄</span>
        )}
      </div>
      <div className="thumbnail-card__body">
        <div className="thumbnail-card__name" title={root}>{root}</div>
        <div className="thumbnail-card__meta">
          {runCount > 0 ? `${runCount} run${runCount !== 1 ? 's' : ''}` : 'not yet transcribed'}
        </div>
      </div>
    </div>
  )
}

function ThumbnailGrid({ roots, onView }) {
  if (!roots || roots.length === 0) return null

  return (
    <div className="section" style={{ marginTop: 'var(--space-4)' }}>
      <div className="section-title">Documents ({roots.length})</div>
      <div className="thumbnail-grid">
        {roots.map((r) => (
          <ThumbnailCard key={r.root} root={r.root} runCount={r.run_count} onView={onView} />
        ))}
      </div>
    </div>
  )
}

export function UploadTab() {
  const queryClient = useQueryClient()
  const setActiveRoot = useAppStore((s) => s.setActiveRoot)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const setError = useAppStore((s) => s.setError)

  const { data: roots, isLoading: rootsLoading } = useRoots()
  const [uploadResult, setUploadResult] = useState(null)

  const uploadMutation = useMutation({
    mutationFn: uploadFiles,
    onSuccess: (data) => {
      setUploadResult(data)
      queryClient.invalidateQueries({ queryKey: ['roots'] })
    },
    onError: (err) => setError(err.message, 'Upload'),
  })

  const handleView = (root) => {
    setActiveRoot(root)
    setActiveTab('analysis')
  }

  return (
    <div>
      <TwoColumn>
        <div className="section">
          <FileDropzone
            onUpload={(files) => uploadMutation.mutate(files)}
            uploading={uploadMutation.isPending}
          />
          <UploadSummary result={uploadResult} />
        </div>
        <div>
          <ModelSettings />
        </div>
      </TwoColumn>

      <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: 'var(--space-4) 0' }} />

      {rootsLoading ? (
        <Spinner label="Loading documents…" />
      ) : (
        <ThumbnailGrid roots={roots} onView={handleView} />
      )}
    </div>
  )
}
