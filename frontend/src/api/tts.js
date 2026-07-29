import api from './client.js'

export async function generateTts(params) {
  const res = await api.post('/tts/generate', params)
  return res.data
}
