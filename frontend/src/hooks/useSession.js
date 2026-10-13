import { useEffect } from 'react'
import { healthCheck, initSession } from '../api/session.js'
import { getAppInfo, getStoredKeys } from '../api/settings.js'
import { useAppStore } from '../store/appStore.js'

export function useSession() {
  const { setSessionId, setError, setAppInfo, loadStoredKeys } = useAppStore()

  useEffect(() => {
    async function init() {
      try {
        await healthCheck()
        const data = await initSession()
        setSessionId(data.session_id)
      } catch {
        setError('Cannot reach the Transcribe-HTR backend. If you started it yourself, make sure the server is running.', 'Startup')
        return
      }
      try {
        const info = await getAppInfo()
        setAppInfo(info)
        if (info.desktop) loadStoredKeys((await getStoredKeys()).keys)
      } catch {
        // Older backend or web mode without /app-info: carry on as web mode.
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
