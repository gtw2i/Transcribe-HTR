import api from './client.js'

/** Comparison settings the server supports: normalization profiles, tokenizers. */
export async function getOptions() {
  const res = await api.get('/consistency/options')
  return res.data
}

/** Every transcription attempt for a document, with §3.1 identifying metadata. */
export async function listAttempts(root) {
  const res = await api.get('/consistency/attempts', { params: { root } })
  return res.data
}

/** One attempt's full text, for inspection before including it (§3.1). */
export async function getAttemptText(root, attemptId, normalizationProfile, tokenizer) {
  const res = await api.get('/consistency/attempt', {
    params: {
      root,
      attempt_id: attemptId,
      normalization_profile: normalizationProfile,
      tokenizer,
    },
  })
  return res.data
}

/**
 * Run the deterministic consistency analysis.
 *
 * Pure and cacheable server-side: the same body always yields the same result,
 * and nothing is written to the document.
 */
export async function analyze(params) {
  const res = await api.post('/consistency/analyze', params, { timeout: 300_000 })
  return res.data
}

/** Two-way difference between attempts, or an attempt and a consensus (§18). */
export async function diff(params) {
  const res = await api.post('/consistency/diff', params)
  return res.data
}

/** Persist an analysis to the document record. Explicit and additive (D11). */
export async function saveAnalysis(params) {
  const res = await api.post('/consistency/save', params)
  return res.data
}

/** Previously saved analyses for a document. */
export async function listSaved(root) {
  const res = await api.get('/consistency/saved', { params: { root } })
  return res.data
}

/** Delete a saved analysis. */
export async function deleteSaved(root, analysisId) {
  const res = await api.delete(`/consistency/saved/${analysisId}`, { params: { root } })
  return res.data
}

/**
 * Download an export bundle (§26). Does not require the analysis to have been
 * saved first — a user may only want the CSVs.
 */
export async function exportBundle(params) {
  const res = await api.post('/consistency/export', params, {
    responseType: 'blob',
    timeout: 300_000,
  })

  const disposition = res.headers['content-disposition'] ?? ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  const filename = match ? match[1] : 'consistency_export.zip'

  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  return filename
}
