import { useState } from 'react'

export function PasswordInput({ label, hint, className = '', ...props }) {
  const [show, setShow] = useState(false)

  return (
    <div className="form-group">
      {label && <label>{label}</label>}
      <div className="password-wrapper">
        <input
          type={show ? 'text' : 'password'}
          className={`form-control ${className}`}
          autoComplete="off"
          {...props}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setShow((s) => !s)}
          tabIndex={-1}
          aria-label={show ? 'Hide password' : 'Show password'}
        >
          {show ? '🙈' : '👁'}
        </button>
      </div>
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  )
}
