import { useEffect } from 'react'
import api from '../api/client.js'
import { desktopBridge } from '../utils/download.js'
import { useAppStore } from '../store/appStore.js'

const HEARTBEAT_MS = 30_000

// Desktop app only: keeps the launcher (desktop/launcher.py) informed.
// - Tracks when pywebview has injected window.pywebview.api (bridgeReady).
// - In the native window: reports whether a transcription batch is running,
//   so closing the window can ask before quitting.
// - In the browser fallback (no native window, so no bridge): sends a
//   heartbeat, because the launcher quits once the tab has been closed.
export function useDesktopShell() {
  const desktop = useAppStore((s) => s.desktop)
  const bridgeReady = useAppStore((s) => s.bridgeReady)
  const setBridgeReady = useAppStore((s) => s.setBridgeReady)
  const busy = useAppStore((s) => s.transcriptionBatch?.currentRoot != null)

  useEffect(() => {
    if (desktopBridge()) {
      setBridgeReady()
      return
    }
    window.addEventListener('pywebviewready', setBridgeReady)
    return () => window.removeEventListener('pywebviewready', setBridgeReady)
  }, [setBridgeReady])

  useEffect(() => {
    if (desktop && bridgeReady) desktopBridge()?.set_busy?.(busy)
  }, [desktop, bridgeReady, busy])

  useEffect(() => {
    if (!desktop || bridgeReady) return
    const beat = () => api.post('/desktop/heartbeat').catch(() => {})
    beat()
    const timer = setInterval(beat, HEARTBEAT_MS)
    return () => clearInterval(timer)
  }, [desktop, bridgeReady])
}
