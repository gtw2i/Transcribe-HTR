// Rebuild a document's transcription list from its saved JSON (after a restart
// or when switching documents).
//
// The Transcription tab calls the API once per requested transcription, so a
// batch of four is saved as four runs with one output each. Every run's outputs
// are therefore collected, in (run, output) order -- the same order the
// Consistency tab uses (backend/analysis/attempts.py) -- not just the last run's.
export function outputsFromSavedRuns(jsonData) {
  const runs = Array.isArray(jsonData?.runs) ? jsonData.runs : []
  const texts = []
  const tokens = { prompt_tokens: 0, completion_tokens: 0, estimated_cost_usd: null, model: '', provider: '' }

  for (const run of runs) {
    if (!run || typeof run !== 'object') continue
    for (const output of run.outputs || []) {
      const text = typeof output === 'string' ? output : output?.text || ''
      if (text.trim()) texts.push(text)
    }
    tokens.prompt_tokens += run.tokens_in || 0
    tokens.completion_tokens += run.tokens_out || 0
    if (run.estimated_cost_usd != null) {
      tokens.estimated_cost_usd = (tokens.estimated_cost_usd || 0) + run.estimated_cost_usd
    }
    tokens.model = run.model || tokens.model
    tokens.provider = run.provider || tokens.provider
  }
  return { texts, tokens }
}
