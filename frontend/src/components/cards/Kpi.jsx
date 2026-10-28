/** Headline number tile. `accent` paints a team-colour top edge; null value shows an em dash. */
export default function Kpi({ label, value, sub, accent }) {
  return (
    <div className="kpi" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value ?? '—'}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}
