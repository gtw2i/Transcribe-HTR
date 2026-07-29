export function Alert({ type = 'info', children }) {
  return <div className={`alert alert-${type}`}>{children}</div>
}
