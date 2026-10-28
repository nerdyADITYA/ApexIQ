import { formatDelta, formatLapTime, interp, stateAt } from '../utils/telemetry.js'

function Readout({ tag, color, info, state }) {
  const pct = (v) => (v == null ? 0 : Math.max(0, Math.min(100, v)))
  return (
    <div className="readout card" style={{ borderTop: `3px solid ${color}` }}>
      <h3>{tag} {info.code} <span className="muted small">lap {info.lap_number} · {formatLapTime(info.lap_time_s)}</span></h3>
      <div className="stats">
        <div className="stat"><div className="stat-value">{state.speed == null ? '—' : Math.round(state.speed)}</div><div className="stat-label">km/h</div></div>
        <div className="stat"><div className="stat-value">{state.gear ?? '—'}</div><div className="stat-label">gear</div></div>
        <div className="stat"><div className="stat-value">{state.rpm == null ? '—' : Math.round(state.rpm)}</div><div className="stat-label">rpm</div></div>
      </div>
      <div className="bar-row"><span>Throttle</span>
        <div className="bar" role="meter" aria-label={`${info.code} throttle`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct(state.throttle))}>
          <div className="bar-fill throttle" style={{ width: `${pct(state.throttle)}%` }} /></div></div>
      <div className="bar-row"><span>Brake</span>
        <div className="bar" role="meter" aria-label={`${info.code} brake`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct((state.brake ?? 0) * 100))}>
          <div className="bar-fill brake" style={{ width: `${pct((state.brake ?? 0) * 100)}%` }} /></div></div>
      {state.finished && <p className="muted small">Lap complete.</p>}
    </div>
  )
}

/** Live readouts at the current playback time, plus the running and final time gap. */
export default function LapComparison({ data, time, colors }) {
  const { samples } = data
  const sa = stateAt(samples.a, samples.distance_m, time)
  const sb = samples.b ? stateAt(samples.b, samples.distance_m, time) : null
  const liveGap = samples.b && sa.distance != null ? interp(samples.distance_m, samples.delta_s, sa.distance) : null
  const finalGap = samples.b ? samples.delta_s[samples.delta_s.length - 1] : null
  return (
    <div>
      <div className="grid">
        <Readout tag="A" color={colors.a} info={data.a} state={sa} />
        {sb && <Readout tag="B" color={colors.b} info={data.b} state={sb} />}
      </div>
      {samples.b && (
        <div className="card">
          <div className="stats">
            <div className="stat" title="Gap measured at the distance where A currently is">
              <div className="stat-value">{formatDelta(liveGap)}</div>
              <div className="stat-label">{data.b.code} vs {data.a.code}, at A's position</div>
            </div>
            <div className="stat">
              <div className="stat-value">{formatDelta(finalGap)}</div>
              <div className="stat-label">full-lap difference</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
