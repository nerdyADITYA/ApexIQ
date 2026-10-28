import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const COLOR_A = '#ff5d5d'
const COLOR_B = '#4dc3ff'
const tip = { contentStyle: { background: '#1b1b22', border: '1px solid #444' } }

/** Merge the distance-aligned samples into row objects for Recharts. */
export function chartRows(data) {
  const { samples } = data
  return samples.distance_m.map((d, i) => ({
    d,
    speedA: samples.a.speed_kph[i], throttleA: samples.a.throttle[i],
    brakeA: samples.a.brake[i] == null ? null : samples.a.brake[i] * 100,
    ...(samples.b && {
      speedB: samples.b.speed_kph[i], throttleB: samples.b.throttle[i],
      brakeB: samples.b.brake[i] == null ? null : samples.b.brake[i] * 100,
      delta: samples.delta_s[i],
    }),
  }))
}

function Panel({ title, rows, lines, unit, cursor, height = 170, yDomain }) {
  return (
    <div className="card chart-panel">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} syncId="lap">
          <CartesianGrid stroke="#333" strokeDasharray="3 3" />
          <XAxis dataKey="d" type="number" domain={[0, 'dataMax']} stroke="#aaa" tickFormatter={(v) => `${Math.round(v)}`} />
          <YAxis stroke="#aaa" domain={yDomain ?? ['auto', 'auto']} unit={unit} width={56} />
          <Tooltip {...tip} labelFormatter={(v) => `${Math.round(v)} m`} formatter={(v) => (v == null ? '—' : Number(v).toFixed(1))} />
          {lines.map((l) => (
            <Line key={l.key} dataKey={l.key} name={l.name} stroke={l.color} dot={false} isAnimationActive={false}
              strokeDasharray={l.dash} connectNulls={false} />
          ))}
          {cursor != null && <ReferenceLine x={cursor} stroke="#fff" strokeDasharray="2 2" />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Speed, throttle, brake and (with two drivers) time-delta traces against lap distance. */
export default function TelemetryCharts({ data, cursorDistance }) {
  const rows = useMemo(() => chartRows(data), [data])
  const two = !!data.samples.b
  const a = data.a.code
  const b = data.b?.code
  const line = (key, name, color, dash) => ({ key, name, color, dash })
  return (
    <div>
      <Panel title="Speed (km/h)" rows={rows} cursor={cursorDistance}
        lines={[line('speedA', `A ${a}`, COLOR_A), ...(two ? [line('speedB', `B ${b}`, COLOR_B, '6 3')] : [])]} />
      <Panel title="Throttle (%)" rows={rows} cursor={cursorDistance} height={120} yDomain={[0, 100]}
        lines={[line('throttleA', `A ${a}`, COLOR_A), ...(two ? [line('throttleB', `B ${b}`, COLOR_B, '6 3')] : [])]} />
      <Panel title="Brake (%)" rows={rows} cursor={cursorDistance} height={100} yDomain={[0, 100]}
        lines={[line('brakeA', `A ${a}`, COLOR_A), ...(two ? [line('brakeB', `B ${b}`, COLOR_B, '6 3')] : [])]} />
      {two && (
        <Panel title={`Time delta: ${b} relative to ${a} (s)`} rows={rows} cursor={cursorDistance} height={140}
          lines={[line('delta', `${b} − ${a}`, '#ffd24d')]} />
      )}
      {two && (
        <p className="muted small">
          Positive delta: {b} is behind {a} at that point of the lap. Traces are aligned by lap distance, with each
          car's integrated distance rescaled to a common {data.compared_length_m.toFixed(0)} m lap; the final delta
          is the full-lap time difference.
        </p>
      )}
    </div>
  )
}
