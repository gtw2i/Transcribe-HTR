import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

export function Modal({ title, onClose, size, children, footer }) {
  const backdropRef = useRef(null)

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function handleBackdropClick(e) {
    if (e.target === backdropRef.current) onClose?.()
  }

  const sizeClass = size === 'sm' ? 'modal-sm' : size === 'lg' ? 'modal-lg' : ''

  return createPortal(
    <div className="modal-backdrop" ref={backdropRef} onClick={handleBackdropClick}>
      <div className={`modal ${sizeClass}`} role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>{title}</h2>
          {onClose && (
            <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
          )}
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  )
}
