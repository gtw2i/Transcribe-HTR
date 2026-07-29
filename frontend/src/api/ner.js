import api from './client.js'

export async function runNer(params) {
  const res = await api.post('/ner', params, { timeout: 300_000 })
  return res.data
}

export async function fetchEntityTypes() {
  const res = await api.get('/ner/entity-types')
  return res.data
}
