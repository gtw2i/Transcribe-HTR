import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getProfile, upsertProfile, deleteProfile } from '../../api/profiles.js'
import { TTS_UI_ENABLED } from '../../featureFlags.js'
import { useAppStore } from '../../store/appStore.js'
import { Modal } from '../shared/Modal.jsx'
import { Button } from '../shared/Button.jsx'
import { TextArea } from '../shared/TextArea.jsx'
import { TwoColumn } from '../shared/TwoColumn.jsx'
import { Alert } from '../shared/Alert.jsx'
import { InlineSpinner } from '../shared/Spinner.jsx'

function makeSlug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

const EMPTY_FIELDS = {
  name: '',
  description: '',
  verbalize_enabled: false,
  system_prompt: '',
  transcription_prompt: '',
  harmonization_system_prompt: '',
  harmonization_prompt: '',
}

export function ProfileEditorModal() {
  const queryClient = useQueryClient()
  const profileEditorMode = useAppStore((s) => s.profileEditorMode)
  const profileEditorSource = useAppStore((s) => s.profileEditorSource)
  const closeProfileEditor = useAppStore((s) => s.closeProfileEditor)
  const setActiveProfile = useAppStore((s) => s.setActiveProfile)
  const setError = useAppStore((s) => s.setError)

  const [fields, setFields] = useState(EMPTY_FIELDS)
  const [initialFields, setInitialFields] = useState(EMPTY_FIELDS)
  const [loading, setLoading] = useState(true)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [validationErrors, setValidationErrors] = useState([])

  const isEdit = profileEditorMode === 'edit'
  const isNew = profileEditorMode === 'new'
  const slug = isEdit ? profileEditorSource : makeSlug(fields.name)

  useEffect(() => {
    if (isNew) {
      setFields(EMPTY_FIELDS)
      setInitialFields(EMPTY_FIELDS)
      setLoading(false)
      return
    }
    async function load() {
      try {
        const data = await getProfile(profileEditorSource)
        const loaded = {
          name: isEdit ? (data.name || profileEditorSource) : `Copy of ${data.name || profileEditorSource}`,
          description: data.description || '',
          verbalize_enabled: data.verbalize_enabled || false,
          system_prompt: data.system_prompt || '',
          transcription_prompt: (data.transcription_prompt || '').replace(/\{\}/g, '').trimEnd(),
          harmonization_system_prompt: data.harmonization_system_prompt || '',
          harmonization_prompt: (data.harmonization_prompt || '').replace(/\{\}/g, '').trimEnd(),
        }
        setFields(loaded)
        setInitialFields(loaded)
      } catch {
        setError('Could not load profile for editing', 'Profile Editor')
        closeProfileEditor()
      } finally {
        setLoading(false)
      }
    }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const isDirty = JSON.stringify(fields) !== JSON.stringify(initialFields)

  function validate() {
    const errors = []
    if (!fields.name.trim()) errors.push('Name is required')
    if (!fields.system_prompt.trim()) errors.push('System prompt is required')
    if (!fields.transcription_prompt.trim()) errors.push('Transcription prompt is required')
    if (!fields.harmonization_system_prompt.trim()) errors.push('Harmonization system prompt is required')
    if (!fields.harmonization_prompt.trim()) errors.push('Harmonization prompt is required')
    return errors
  }

  const saveMutation = useMutation({
    mutationFn: () => upsertProfile(slug, {
      ...fields,
      transcription_prompt: fields.transcription_prompt.trimEnd() + '\n{}',
      harmonization_prompt: fields.harmonization_prompt.trimEnd() + '\n{}',
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      queryClient.invalidateQueries({ queryKey: ['profile', slug] })
      if (!isEdit) setActiveProfile(slug)
      closeProfileEditor()
    },
    onError: (err) => setError(err.message, 'Profile Save'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteProfile(profileEditorSource),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      closeProfileEditor()
    },
    onError: (err) => setError(err.message, 'Profile Delete'),
  })

  const handleSave = () => {
    const errors = validate()
    setValidationErrors(errors)
    if (errors.length === 0) saveMutation.mutate()
  }

  const handleCancel = () => {
    if (isDirty) setConfirmCancel(true)
    else closeProfileEditor()
  }

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setFields((f) => ({ ...f, [key]: value }))
  }

  const title = isEdit
    ? `✏️ Edit Profile: ${fields.name}`
    : isNew
    ? `✏️ New Profile`
    : `📋 Clone Profile from: ${profileEditorSource}`

  return (
    <Modal
      title={title}
      onClose={handleCancel}
      size="lg"
      footer={
        <>
          {isEdit && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setConfirmDelete(true)}
              style={{ marginRight: 'auto' }}
            >
              🗑️ Delete
            </Button>
          )}
          <Button variant="secondary" onClick={handleCancel}>Cancel</Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={saveMutation.isPending || validationErrors.length > 0}
          >
            {saveMutation.isPending ? <><InlineSpinner /> Saving…</> : '💾 Save'}
          </Button>
        </>
      }
    >
      {loading ? (
        <div style={{ padding: 'var(--space-5)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
          Loading profile…
        </div>
      ) : (
        <div>
          {validationErrors.length > 0 && (
            <Alert type="error">
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </Alert>
          )}

          <div className="form-group">
            <label>Profile Name{!isEdit && ' (new profile)'}</label>
            <input
              className="form-control"
              value={fields.name}
              onChange={set('name')}
              disabled={isEdit}
              placeholder="My Custom Profile"
            />
            {!isEdit && fields.name && (
              <div className="form-hint">Slug: <code>{slug}</code></div>
            )}
          </div>

          <div className="form-group">
            <label>Description (optional)</label>
            <input className="form-control" value={fields.description} onChange={set('description')} />
          </div>

          {TTS_UI_ENABLED && (
            <label className="checkbox-label" style={{ marginBottom: 'var(--space-3)' }}>
              <input type="checkbox" checked={fields.verbalize_enabled} onChange={set('verbalize_enabled')} />
              Enable Text-to-Speech (Verbalize) for this profile
            </label>
          )}

          <TwoColumn>
            <div>
              <TextArea label="Transcription System Prompt" value={fields.system_prompt} onChange={set('system_prompt')} style={{ height: 120 }} />
              <TextArea label="Transcription User Prompt" value={fields.transcription_prompt} onChange={set('transcription_prompt')} style={{ height: 180 }} hint="Your domain knowledge will be appended automatically." />
            </div>
            <div>
              <TextArea label="Harmonization System Prompt" value={fields.harmonization_system_prompt} onChange={set('harmonization_system_prompt')} style={{ height: 120 }} />
              <TextArea label="Harmonization User Prompt" value={fields.harmonization_prompt} onChange={set('harmonization_prompt')} style={{ height: 180 }} hint="The transcriptions will be appended automatically." />
            </div>
          </TwoColumn>

          {confirmCancel && (
            <div className="alert alert-warning" style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
              <span style={{ flex: 1 }}>You have unsaved changes. Discard them?</span>
              <Button variant="secondary" size="sm" onClick={() => setConfirmCancel(false)}>Keep Editing</Button>
              <Button variant="danger" size="sm" onClick={closeProfileEditor}>Discard & Close</Button>
            </div>
          )}

          {confirmDelete && (
            <div className="alert alert-error" style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
              <span style={{ flex: 1 }}>⚠️ Delete this profile permanently?</span>
              <Button variant="secondary" size="sm" onClick={() => setConfirmDelete(false)}>Cancel</Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? <><InlineSpinner /> Deleting…</> : '⚠️ Confirm Delete'}
              </Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
