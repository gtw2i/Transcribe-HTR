import { useState } from 'react'
import { useAppStore } from '../../store/appStore.js'
import { desktopBridge } from '../../utils/download.js'
import { Button } from './Button.jsx'

// Desktop-app-only helpers backed by desktop/bridge.py. Each renders nothing
// in a browser, where the bridge does not exist.

/** "Your data on this computer": where things are kept, plus support tools. */
export function DesktopDataCard() {
  const desktop = useAppStore((s) => s.desktop)
  const appInfo = useAppStore((s) => s.appInfo)
  const [diagnostics, setDiagnostics] = useState('')
  const [copied, setCopied] = useState(false)
  const bridgeReady = useAppStore((s) => s.bridgeReady)
  const bridge = desktopBridge()
  if (!desktop || !bridgeReady || !bridge) return null

  const copyDiagnostics = async () => {
    const text = await bridge.diagnostics()
    setDiagnostics(text)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Clipboard blocked: the text is shown below for manual copying.
    }
  }

  return (
    <div className="card section">
      <div className="section-title">💾 Your data on this computer</div>
      <p style={{ lineHeight: 1.7 }}>
        Your documents and results are saved automatically and are still here the next time you
        open Transcribe-HTR. They are private to your user account on this computer.
      </p>
      {appInfo?.workspace_dir && (
        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', wordBreak: 'break-all' }}>
          {appInfo.workspace_dir}
        </p>
      )}
      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
        <Button variant="secondary" size="sm" onClick={() => bridge.open_folder('workspace')}>📂 Open documents folder</Button>
        <Button variant="ghost" size="sm" onClick={() => bridge.open_folder('logs')}>📄 Open log folder</Button>
        <Button variant="ghost" size="sm" onClick={copyDiagnostics}>{copied ? '✅ Copied' : '🩺 Copy diagnostics'}</Button>
      </div>
      {diagnostics && (
        <textarea
          className="form-control"
          readOnly
          rows={6}
          value={diagnostics}
          style={{ marginTop: 'var(--space-2)', fontFamily: 'monospace', fontSize: 'var(--font-size-sm)' }}
          onFocus={(e) => e.target.select()}
        />
      )}
    </div>
  )
}

/** After a save in the desktop app: the file name and a "Show in folder" link. */
export function SavedFileNotice({ result }) {
  const bridge = desktopBridge()
  if (!result || result.status !== 'saved' || !result.path || !bridge) return null
  return (
    <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-sm)', display: 'flex', gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
      <span>✅ Saved <strong>{result.name}</strong></span>
      <Button variant="ghost" size="sm" onClick={() => bridge.reveal(result.path)}>Show in folder</Button>
    </div>
  )
}
