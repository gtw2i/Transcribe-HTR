import api from './client.js'

export async function exportAll(format = 'json') {
  const res = await api.get('/export', {
    params: { format },
    responseType: 'blob',
  })
  return res
}
