import api from './client.js'

export async function listProfiles() {
  const res = await api.get('/profiles')
  return res.data
}

export async function getProfile(slug) {
  const res = await api.get(`/profiles/${encodeURIComponent(slug)}`)
  return res.data
}

export async function upsertProfile(slug, data) {
  const res = await api.post('/profiles', { slug, ...data })
  return res.data
}

export async function deleteProfile(slug) {
  const res = await api.delete(`/profiles/${encodeURIComponent(slug)}`)
  return res.data
}
