import { useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import { sessionName } from '../utils/sessions.js'
import QueryState from '../components/common/QueryState.jsx'

const COLORS = ['#ff4d4d', '#4dc3ff', '#ffd24d', '#7dff9b', '#c28bff', '#ff9f4d']

const SEVERITY = { vsc: 1, sc: 2, red: 3 }
export const NEUTRAL_LABELS = { vsc: 'Virtual safety car', sc: 'Safety car', red: 'Red flag' }
const BAND_SHORT = { vsc: 'VSC', sc: 'SC', red: 'Red flag' }
const BAND_COLORS = { vsc: '#ffd24d', sc: '#ff9f4d', red: '#ff4d4d' }

/**
 * Which neutralisation a lap's track-status string contains (codes seen during the lap):
 * 5 red flag, 4 safety car, 6/7 virtual safety car (7 = VSC ending). Yellow (2) alone is not neutralised.
 */
export function neutralKind(status) {
  const s = String(status ?? '')
  if (s.includes('5')) return 'red'
  if (s.includes('4')) return 'sc'
  if (s.includes('6') || s.includes('7')) return 'vsc'
  return null
}

/** [11,12,13,14,16] -> "11–14, 16" */
export function formatRanges(nums) {
  const out = []
  let start = null
  let prev = null
  for (const n of [...nums].sort((a, b) => a - b)) {
    if (start === null) { start = prev = n } else if (n === prev + 1) { prev = n } else { out.push([start, prev]); start = prev = n }
  }
  if (start !== null) out.push([start, prev])
  return out.map(([a, b]) => (a === b ? `${a}` : `${a}–${b}`)).join(', ')
}

/**
 * What explains the gaps: shaded bands for laps run under a virtual safety car / safety car / red flag
 * (worst condition wins when the selected drivers' laps disagree, since lap boundaries differ per driver),
 * and each driver's pit stops. A stop is the first lap of a run of consecutive pit laps (in-lap, then out-lap);
 * a lone pit lap on lap 1 is a pit-lane start, not a stop.
 */
export function lapAnnotations(laps, drivers) {
  const mine = laps.filter((l) => drivers.includes(l.driver))
  const kindByLap = new Map()
  for (const l of mine) {
    const k = neutralKind(l.track_status)
    if (k && (!kindByLap.has(l.lap_number) || SEVERITY[k] > SEVERITY[kindByLap.get(l.lap_number)])) kindByLap.set(l.lap_number, k)
  }
  const bands = []
  for (const lap of [...kindByLap.keys()].sort((a, b) => a - b)) {
    const kind = kindByLap.get(lap)
    const last = bands.at(-1)
    if (last && last.kind === kind && last.to === lap - 1) last.to = lap
    else bands.push({ kind, from: lap, to: lap })
  }
  const pits = []
  for (const driver of drivers) {
    const pitLaps = [...new Set(mine.filter((l) => l.driver === driver && l.is_pit_lap).map((l) => l.lap_number))].sort((a, b) => a - b)
    let i = 0
    while (i < pitLaps.length) {
      let j = i
      while (j + 1 < pitLaps.length && pitLaps[j + 1] === pitLaps[j] + 1) j++
      if (!(i === j && pitLaps[i] === 1)) pits.push({ driver, lap: pitLaps[i] })
      i = j + 1
    }
  }
  return { bands, pits }
}

/** Sessions that are a continuous race (one lap after another); everything else is a set of separate attempts. */
export const isRaceLike = (type) => type === 'R' || type === 'S'

/** Drop laps slower than `ratio` x the driver's own best lap (cool-down and traffic-affected laps). */
export function filterSlow(laps, ratio) {
  const best = {}
  for (const l of laps) {
    if (l.lap_time_s != null && l.is_valid !== false && (best[l.driver] == null || l.lap_time_s < best[l.driver])) best[l.driver] = l.lap_time_s
  }
  const kept = laps.filter((l) => l.lap_time_s == null || l.lap_time_s <= best[l.driver] * ratio)
  return { laps: kept, hidden: laps.filter((l) => l.lap_time_s != null).length - kept.filter((l) => l.lap_time_s != null).length }
}

/**
 * Pivot [{driver, lap_number, lap_time_s}] into [{lap, DRV1: t, DRV2: t}].
 * With `fillGaps`, every lap number in range gets a row, so a lap with no valid time shows as a real
 * gap instead of the line silently joining its neighbours (used for races).
 */
export function pivotLaps(laps, drivers, { fillGaps = false } = {}) {
  const byLap = new Map()
  for (const l of laps) {
    if (!drivers.includes(l.driver) || l.lap_time_s == null || l.is_valid === false) continue
    const row = byLap.get(l.lap_number) ?? { lap: l.lap_number }
    row[l.driver] = l.lap_time_s
    byLap.set(l.lap_number, row)
  }
  if (fillGaps && byLap.size) {
    const nums = [...byLap.keys()]
    for (let n = Math.min(...nums); n <= Math.max(...nums); n++) if (!byLap.has(n)) byLap.set(n, { lap: n })
  }
  return [...byLap.values()].sort((a, b) => a.lap - b.lap)
}

export default function RaceExplorer() {
  const { year } = useSeason()
  const [sessionId, setSessionId] = useState('')
  const [selected, setSelected] = useState([])
  const [hideSlowChoice, setHideSlowChoice] = useState(false)

  const events = useQuery({ queryKey: ['events', year], queryFn: () => api.events(year), enabled: !!year })
  const drivers = useQuery({
    queryKey: ['drivers', sessionId], queryFn: () => api.sessionDrivers(sessionId), enabled: !!sessionId,
  })
  // One request per selected driver: the API caps page size, so a whole-session fetch silently truncates.
  const lapQueries = useQueries({
    queries: selected.map((code) => ({
      queryKey: ['laps', sessionId, code], queryFn: () => api.laps(sessionId, code), enabled: !!sessionId,
    })),
  })
  const laps = {
    isLoading: lapQueries.some((q) => q.isLoading),
    isError: lapQueries.some((q) => q.isError),
    error: lapQueries.find((q) => q.isError)?.error,
    data: { laps: lapQueries.flatMap((q) => q.data?.laps ?? []) },
  }

  const loaded = (events.data ?? []).flatMap((e) =>
    e.sessions.filter((s) => s.status === 'loaded' && s.type === 'R').map((s) => ({ ...s, label: `R${e.round} ${e.name} · ${sessionName(s.type)}` })),
  )
  const hideSlow = hideSlowChoice
  const toggle = (code) =>
    setSelected((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code].slice(-6)))

  return (
    <section>
      <PageHeader eyebrow="Race explorer" title="Lap times by race" />
      <QueryState query={events} empty={() => false}>
        {() => (
          <label>
            Session{' '}
            <select value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSelected([]); setHideSlowChoice(false) }}>
              <option value="">Select…</option>
              {loaded.map((s) => <option key={s.session_id} value={s.session_id}>{s.label}</option>)}
            </select>
          </label>
        )}
      </QueryState>

      {sessionId && (
        <QueryState query={drivers}>
          {(list) => (
            <div className="chips" role="group" aria-label="Drivers">
              {list.map((d) => (
                <button key={d.code} className={selected.includes(d.code) ? 'chip on' : 'chip'}
                  aria-pressed={selected.includes(d.code)} onClick={() => toggle(d.code)}>
                  {d.code}
                </button>
              ))}
            </div>
          )}
        </QueryState>
      )}

      {sessionId && (
        <QueryState query={laps}>
          {(d) => {
            const validLaps = d.laps.filter((l) => l.is_valid !== false)
            const filtered = hideSlow ? filterSlow(validLaps, 1.07) : { laps: validLaps, hidden: 0 }
            const data = pivotLaps(filtered.laps, selected, { fillGaps: true })
            const ann = lapAnnotations(d.laps, selected)
            const colorOf = (code) => COLORS[selected.indexOf(code)]
            return selected.length === 0 ? (
              <p className="muted">Pick up to six drivers to plot valid-lap times.</p>
            ) : (
              <div className="card">
                <h2>Lap time by lap (s)</h2>
                <label className="inline-check">
                  <input type="checkbox" checked={hideSlow} onChange={(e) => setHideSlowChoice(e.target.checked)} />
                  Hide laps slower than 107% of each driver's best
                  {filtered.hidden > 0 && <span className="muted small"> ({filtered.hidden} hidden)</span>}
                </label>
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="lap" type="number" domain={['dataMin', 'dataMax']} allowDecimals={false} stroke="#aaa" />
                    <YAxis domain={['auto', 'auto']} stroke="#aaa" />
                    <Tooltip contentStyle={{ background: '#1b1b22', border: '1px solid #444' }}
                      labelFormatter={(v) => `Lap ${v}`} formatter={(v) => (v == null ? '—' : `${Number(v).toFixed(3)} s`)} />
                    <Legend />
                    {ann.bands.map((b) => (
                      <ReferenceArea key={`${b.kind}-${b.from}`} x1={b.from - 0.5} x2={b.to + 0.5} ifOverflow="hidden"
                        fill={BAND_COLORS[b.kind]} fillOpacity={0.14} stroke="none"
                        label={{ value: BAND_SHORT[b.kind], position: 'insideTop', fill: BAND_COLORS[b.kind], fontSize: 11 }} />
                    ))}
                    {ann.pits.map((p) => (
                      <ReferenceLine key={`${p.driver}-${p.lap}`} x={p.lap + 0.5} stroke={colorOf(p.driver)}
                        strokeDasharray="2 3" ifOverflow="hidden" />
                    ))}
                    {selected.map((c, i) => (
                      <Line key={c} isAnimationActive={false} dataKey={c} stroke={COLORS[i]}
                        dot={false} connectNulls={false}
                        strokeDasharray={i % 2 ? '5 3' : undefined} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
                <ul className="gapkey" aria-label="Why laps are missing">
                  {Object.keys(NEUTRAL_LABELS).filter((k) => ann.bands.some((x) => x.kind === k)).map((k) => (
                    <li key={k}>
                      <i className="gapkey-swatch" style={{ background: BAND_COLORS[k] }} aria-hidden="true" />
                      <b>{NEUTRAL_LABELS[k]}</b>: laps {formatRanges(ann.bands.filter((x) => x.kind === k).flatMap((x) => Array.from({ length: x.to - x.from + 1 }, (_, i) => x.from + i)))}
                    </li>
                  ))}
                  {ann.pits.length > 0 && (
                    <li>
                      <i className="gapkey-swatch dashed" aria-hidden="true" />
                      <b>Pit stops</b> (dashed lines):{' '}
                      {ann.pits.map((p, i) => (
                        <span key={`${p.driver}-${p.lap}`} style={{ color: colorOf(p.driver) }}>{i > 0 && ', '}{p.driver} lap {p.lap}</span>
                      ))}
                    </li>
                  )}
                </ul>
                <p className="muted small">
                  The lines show valid laps only. Gaps are laps left out as pit in/out laps, or run under a virtual
                  safety car, safety car or red flag (shaded). Yellow flags alone don't exclude a lap.
                </p>
              </div>
            )
          }}
        </QueryState>
      )}
    </section>
  )
}
