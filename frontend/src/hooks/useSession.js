import { useEffect } from 'react'
import { healthCheck, initSession } from '../api/session.js'
import { useAppStore } from '../store/appStore.js'

export function useSession() {
  const { setSessionId, setError } = useAppStore()

  useEffect(() => {
    async function init() {
      try {
        await healthCheck()
        const data = await initSession()
        setSessionId(data.session_id)
      } catch {
        setError('Cannot reach the backend. Make sure the FastAPI server is running on port 8000.', 'Startup')
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
