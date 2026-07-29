import api from './client.js'

export async function summarize(params) {
  const res = await api.post('/summarize', params, { timeout: 120_000 })
  return res.data
}
