export function Select({ label, hint, options = [], className = '', ...props }) {
  return (
    <div className="form-group">
      {label && <label>{label}</label>}
      <select className={`form-control ${className}`} {...props}>
        {options.map((opt) => {
          const value = typeof opt === 'string' ? opt : opt.value
          const text = typeof opt === 'string' ? opt : opt.label
          return <option key={value} value={value}>{text}</option>
        })}
      </select>
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  )
}
