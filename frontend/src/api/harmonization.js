import api from './client.js'

export async function harmonize(params) {
  const res = await api.post('/harmonize', params, { timeout: 300_000 })
  return res.data
}
