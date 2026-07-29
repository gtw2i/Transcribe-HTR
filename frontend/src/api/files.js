import api from './client.js'

export async function listRoots() {
  const res = await api.get('/files/roots')
  return res.data
}

export async function getImage(root) {
  const res = await api.get(`/files/${encodeURIComponent(root)}/image`)
  return res.data
}

export async function getJson(root) {
  const res = await api.get(`/files/${encodeURIComponent(root)}/json`)
  return res.data
}

export async function getSummary(root) {
  const res = await api.get(`/files/${encodeURIComponent(root)}/summary`)
  return res.data
}

export async function uploadFiles(files) {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  const res = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}
