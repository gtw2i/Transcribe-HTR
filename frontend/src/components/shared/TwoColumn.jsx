export function TwoColumn({ children, variant, style }) {
  const cls = ['two-col', variant === 'wide' ? 'two-col-wide' : variant === 'narrow' ? 'two-col-narrow' : ''].filter(Boolean).join(' ')
  return <div className={cls} style={style}>{children}</div>
}
