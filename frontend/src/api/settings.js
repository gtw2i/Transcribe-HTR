import api from './client.js'

// { version, desktop, data_dir?, workspace_dir?, log_dir?, secret_backend? }
export async function getAppInfo() {
  const res = await api.get('/app-info')
  return res.data
}

// Desktop only: { backend, keys: { openai, gemini, anthropic } }
export async function getStoredKeys() {
  const res = await api.get('/settings/keys')
  return res.data
}

// An empty key forgets the stored one.
export async function storeKey(provider, key) {
  const res = await api.put(`/settings/keys/${provider}`, { key })
  return res.data
}
