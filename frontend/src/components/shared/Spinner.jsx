export function Spinner({ size, label }) {
  return (
    <div className="spinner-overlay">
      <span className={`spinner${size === 'lg' ? ' spinner-lg' : ''}`} aria-hidden="true" />
      {label && <span>{label}</span>}
    </div>
  )
}

export function InlineSpinner() {
  return <span className="spinner" aria-hidden="true" style={{ display: 'inline-block', verticalAlign: 'middle' }} />
}
