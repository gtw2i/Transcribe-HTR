import api from './client.js'

export async function colorize(params) {
  const res = await api.post('/colorize', params)
  return res.data
}
