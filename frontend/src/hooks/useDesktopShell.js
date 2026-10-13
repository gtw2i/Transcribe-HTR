import { useEffect } from 'react'
import api from '../api/client.js'
import { desktopBridge } from '../utils/download.js'
import { useAppStore } from '../store/appStore.js'

const HEARTBEAT_MS = 30_000

// Desktop app only: keeps the launcher (desktop/launcher.py) informed.
// - In the native window: reports whether a transcription batch is running,
//   so closing the window can ask before quitting.
// - In the browser fallback (no native window): sends a heartbeat, because
//   the launcher quits once the tab has been closed for a while.
export function useDesktopShell() {
  const desktop = useAppStore((s) => s.desktop)
  const busy = useAppStore((s) => s.transcriptionBatch !== null && s.transcriptionBatch?.currentRoot != null)

  useEffect(() => {
    if (!desktop) return
    desktopBridge()?.set_busy?.(busy)
  }, [desktop, busy])

  useEffect(() => {
    if (!desktop || desktopBridge()) return
    const beat = () => api.post('/desktop/heartbeat').catch(() => {})
    beat()
    const timer = setInterval(beat, HEARTBEAT_MS)
    return () => clearInterval(timer)
  }, [desktop])
}
