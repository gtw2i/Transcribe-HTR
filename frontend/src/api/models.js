import api from './client.js'

export async function fetchModels(provider, apiKey) {
  const res = await api.post('/models', { provider, api_key: apiKey })
  return res.data
}
