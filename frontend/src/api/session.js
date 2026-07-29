import api from './client.js'

export async function healthCheck() {
  const res = await api.get('/health')
  return res.data
}

export async function initSession() {
  const res = await api.post('/session/init')
  return res.data
}
