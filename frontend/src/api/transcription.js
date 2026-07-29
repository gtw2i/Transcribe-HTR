import api from './client.js'

export async function transcribe(params) {
  const res = await api.post('/transcribe', params, { timeout: 300_000 })
  return res.data
}
