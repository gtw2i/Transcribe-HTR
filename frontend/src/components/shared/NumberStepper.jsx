export function NumberStepper({ label, value, min = 1, max = 10, onChange }) {
  return (
    <div className="form-group" style={{ width: 'fit-content' }}>
      {label && <label>{label}</label>}
      <div className="number-stepper">
        <button type="button" onClick={() => onChange(Math.max(min, value - 1))} disabled={value <= min}>−</button>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10)
            if (!isNaN(v)) onChange(Math.min(max, Math.max(min, v)))
          }}
        />
        <button type="button" onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}>+</button>
      </div>
    </div>
  )
}
