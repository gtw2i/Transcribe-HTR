import { useAppStore } from '../../store/appStore.js'

export function ErrorBanner() {
  const errorBanner = useAppStore((s) => s.errorBanner)
  const clearError = useAppStore((s) => s.clearError)

  if (!errorBanner) return null

  return (
    <>
    <div className="error-backdrop" />
    <div className="error-banner">
      <span className="error-banner-text">
        {errorBanner.context && (
          <span className="error-banner-context">{errorBanner.context}: </span>
        )}
        {errorBanner.message}
      </span>
      <button
        onClick={clearError}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'inherit', padding: '0 4px' }}
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
    </>
  )
}
