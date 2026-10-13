import api from '../api/client.js'

// The desktop app's Python bridge (desktop/bridge.py), when running inside it.
export function desktopBridge() {
  return window.pywebview?.api ?? null
}

function filenameFrom(disposition, fallback) {
  const match = /filename="?([^";]+)"?/.exec(disposition || '')
  return match ? match[1] : fallback
}

/**
 * Download an API response as a file the user keeps.
 *
 * In the desktop app, Python fetches the file itself and shows the native
 * Save dialog (embedded webviews handle blob-URL downloads inconsistently, and
 * large DOCX/ZIP exports should not cross the JS bridge as base64). In a
 * browser it uses a blob URL and <a download>.
 *
 * Resolves to { status: 'saved', name, path? } or { status: 'cancelled' }.
 */
export async function downloadFromApi({ method = 'GET', path, params, body, fallbackName, timeout }) {
  const bridge = desktopBridge()
  if (bridge?.save_from_api) {
    const result = await bridge.save_from_api({
      method,
      path: `/api${path}`,
      params: params ?? {},
      body: body ?? null,
      fallback_name: fallbackName,
    })
    if (result?.status === 'error') throw new Error(result.message || 'Could not save the file.')
    return result
  }

  const res = await api.request({ method, url: path, params, data: body, responseType: 'blob', timeout })
  const name = filenameFrom(res.headers['content-disposition'], fallbackName)
  const url = URL.createObjectURL(res.data)
  const link = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Revoking immediately can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
  return { status: 'saved', name }
}
