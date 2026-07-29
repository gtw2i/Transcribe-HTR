export function TextArea({ label, hint, showCount, className = '', style, ...props }) {
  const len = typeof props.value === 'string' ? props.value.length : 0

  return (
    <div className="form-group">
      {(label || showCount) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          {label && <label style={{ margin: 0 }}>{label}</label>}
          {showCount && <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>{len.toLocaleString()} chars</span>}
        </div>
      )}
      <textarea className={`form-control ${className}`} style={style} {...props} />
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  )
}
