import { useEffect, useRef } from 'react'
import { storeKey } from '../api/settings.js'
import { useAppStore } from '../store/appStore.js'

const FIELDS = { openai: 'openaiApiKey', gemini: 'geminiApiKey', anthropic: 'anthropicApiKey' }
const SAVE_DELAY_MS = 800

// Desktop app only: keeps the OS credential store / private key file in step
// with the key fields. Mounted once at the app root so it keeps working while
// the Upload tab (where keys are typed) is not shown.
export function useRememberedKeys() {
  const desktop = useAppStore((s) => s.desktop)
  const loaded = useAppStore((s) => s.storedKeysLoaded)
  const remember = useAppStore((s) => s.rememberKeys)
  const keys = {
    openai: useAppStore((s) => s.openaiApiKey),
    gemini: useAppStore((s) => s.geminiApiKey),
    anthropic: useAppStore((s) => s.anthropicApiKey),
  }
  const saved = useRef(null)

  useEffect(() => {
    if (!desktop || !loaded) return
    // First run after loading: what is in the fields is what is stored.
    if (saved.current === null) {
      saved.current = { ...keys }
      return
    }
    const target = remember ? keys : { openai: '', gemini: '', anthropic: '' }
    const changed = Object.keys(FIELDS).filter((p) => target[p] !== saved.current[p])
    if (changed.length === 0) return
    const timer = setTimeout(() => {
      for (const p of changed) {
        storeKey(p, target[p])
          .then(() => { saved.current[p] = target[p] })
          .catch(() => useAppStore.getState().setError('Could not save the API key on this computer.', 'Settings'))
      }
    }, SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [desktop, loaded, remember, keys.openai, keys.gemini, keys.anthropic]) // eslint-disable-line react-hooks/exhaustive-deps
}
