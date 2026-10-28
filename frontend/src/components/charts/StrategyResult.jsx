import {
  Area, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import StintTimeline from './StintTimeline.jsx'

const WHAT_IF = '#4dc3ff'
const ACTUAL = '#ffb347'
const tip = { contentStyle: { background: '#1c2028', border: '1px solid #2f343d' } }

/** Rows for the charts: running difference with its band, and both strategies' modelled pace. */
export function profileRows(profile) {
  return profile.map((p) => ({
    lap: p.lap,
    delta: p.cumulative_delta_s,
    band: [p.cumulative_delta_s - p.band_s, p.cumulative_delta_s + p.band_s],
    actual: p.actual_pace_s,
    whatIf: p.candidate_pace_s,
  }))
}

/** A stop happens at the end of each stint except the last. */
export const stopLaps = (stints) => stints.slice(0, -1).map((s) => s.end_lap)

/** Colour the headline only when the whole 90% interval is on one side of zero; otherwise it is not a clear result. */
export function verdictTone(r) {
  const [lo, hi] = r.uncertainty_interval_seconds
  if (hi < 0) return 'good'
  if (lo > 0) return 'bad'
  return 'neutral'
}

/** One-line verdict. The interval is the model's own 90% range, so a range spanning zero is called out. */
export function verdictText(r) {
  const d = r.baseline_delta_seconds
  if (d == null) return ''
  const [lo, hi] = r.uncertainty_interval_seconds
  const size = `${Math.abs(d).toFixed(1)} s`
  const dir = d === 0 ? 'the same as' : d < 0 ? `${size} faster than` : `${size} slower than`
  const unclear = lo < 0 && hi > 0
  return `The what-if is estimated ${dir} the actual strategy${unclear ? ', but this is within the model\'s uncertainty' : ''}.`
}

export default function StrategyResult({ result: r }) {
  const rows = profileRows(r.profile)
  const total = r.profile.length
  const whatIfStops = stopLaps(r.stints)
  const actualStops = stopLaps(r.actual_stints)
  const [lo, hi] = r.uncertainty_interval_seconds

  return (
    <div className="stratres">
      <div className="verdict">
        <div className="verdict-num" data-tone={verdictTone(r)}>
          {r.baseline_delta_seconds > 0 ? '+' : ''}{r.baseline_delta_seconds.toFixed(1)} s
        </div>
        <div>
          <p className="verdict-text">{verdictText(r)}</p>
          <p className="muted small">
            90% interval {lo.toFixed(1)} to {hi.toFixed(1)} s (negative = faster). Both plans use the same model, so this is
            a model comparison, not a prediction of the real race.
          </p>
        </div>
      </div>

      <div className="plans" aria-label="Tyre plans">
        <div><span className="plan-label">Actual</span><StintTimeline stints={r.actual_stints.map((s, i) => ({ ...s, stint: i }))} totalLaps={total} /></div>
        <div><span className="plan-label">What-if</span><StintTimeline stints={r.stints.map((s, i) => ({ ...s, stint: i }))} totalLaps={total} /></div>
      </div>

      <h3>Running time difference (what-if minus actual)</h3>
      <p className="muted small">
        Above zero the what-if is behind, below zero it is ahead. Each step is a pit stop paying about {r.pit_loss_seconds?.toFixed(0)} s;
        the shaded band is the model's 90% range and widens with every lap.
      </p>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#262a33" strokeDasharray="3 3" />
          <XAxis dataKey="lap" type="number" domain={[1, total]} allowDecimals={false} stroke="#7c8594" />
          <YAxis stroke="#7c8594" width={48} unit=" s" tickFormatter={(v) => Math.round(v)} />
          <Tooltip {...tip} labelFormatter={(v) => `After lap ${v}`}
            formatter={(v, name) => (name === 'range' ? [`${v[0].toFixed(1)} to ${v[1].toFixed(1)} s`, '90% range'] : [`${Number(v).toFixed(1)} s`, 'Difference'])} />
          <ReferenceLine y={0} stroke="#aab2c0" label={{ value: 'even', position: 'insideTopLeft', fill: '#aab2c0', fontSize: 11 }} />
          {actualStops.map((l) => <ReferenceLine key={`a${l}`} x={l} stroke={ACTUAL} strokeDasharray="2 3" />)}
          {whatIfStops.map((l) => <ReferenceLine key={`w${l}`} x={l} stroke={WHAT_IF} strokeDasharray="5 3" />)}
          <Area dataKey="band" name="range" stroke="none" fill={WHAT_IF} fillOpacity={0.15} isAnimationActive={false} />
          <Line dataKey="delta" name="delta" stroke="#ffffff" strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="muted small">
        Dashed vertical lines: <span style={{ color: ACTUAL }}>actual stops (lap {actualStops.join(', ') || 'none'})</span>,{' '}
        <span style={{ color: WHAT_IF }}>what-if stops (lap {whatIfStops.join(', ') || 'none'})</span>.
      </p>

      <h3>Modelled lap times (pit stop time not included)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#262a33" strokeDasharray="3 3" />
          <XAxis dataKey="lap" type="number" domain={[1, total]} allowDecimals={false} stroke="#7c8594" />
          <YAxis stroke="#7c8594" width={48} domain={['auto', 'auto']} tickFormatter={(v) => v.toFixed(0)} />
          <Tooltip {...tip} labelFormatter={(v) => `Lap ${v}`} formatter={(v) => `${Number(v).toFixed(2)} s`} />
          <Legend />
          <Line dataKey="actual" name="Actual" stroke={ACTUAL} dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="whatIf" name="What-if" stroke={WHAT_IF} dot={false} strokeWidth={2} strokeDasharray="5 3" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="muted small">Pace falls as fuel burns off and rises as tyres wear; a fresh set resets the wear.</p>
    </div>
  )
}
