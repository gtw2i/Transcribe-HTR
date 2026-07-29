export function Expander({ title, children, defaultOpen = false, className = '' }) {
  return (
    <details className={`expander ${className}`} open={defaultOpen}>
      <summary>{title}</summary>
      <div className="expander-content">{children}</div>
    </details>
  )
}
