const LETTER = { SOFT: 'S', MEDIUM: 'M', HARD: 'H', INTERMEDIATE: 'I', WET: 'W' }

/** Tyre stints as proportional bars. Compound is shown as text as well as colour. */
export default function StintTimeline({ stints, totalLaps }) {
  if (!stints?.length) return <span className="muted small">no stint data</span>
  const total = totalLaps ?? Math.max(...stints.map((s) => s.end_lap))
  return (
    <div
      className="stints"
      role="img"
      aria-label={stints.map((s) => `${s.compound ?? 'unknown'} laps ${s.start_lap}-${s.end_lap}`).join(', ')}
    >
      {stints.map((s) => (
        <div
          key={s.stint}
          className={`stint ${(s.compound ?? 'unknown').toLowerCase()}`}
          style={{ width: `${((s.end_lap - s.start_lap + 1) / total) * 100}%` }}
          title={`${s.compound ?? 'unknown'}: laps ${s.start_lap}-${s.end_lap}`}
        >
          {LETTER[s.compound] ?? '?'}
        </div>
      ))}
    </div>
  )
}
