/** Labelled number; null renders as an em dash, never as 0. */
export default function Stat({ label, value, unit = '', digits = 1, hint }) {
  const shown =
    value == null ? '—' : typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(digits) : value
  return (
    <div className="stat" title={hint}>
      <div className="stat-value">{shown}{value != null && unit}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
