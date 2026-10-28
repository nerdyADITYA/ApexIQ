import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../services/api.js'
import PageHeader from '../components/layout/PageHeader.jsx'
import StrategyResult from '../components/charts/StrategyResult.jsx'
import { useSeason } from '../hooks/useSeason.jsx'

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD']
const MIN_STINT = 3 // mirrors the backend rule
const MAX_STOPS = 4

/** The driver's real strategy, rebuilt from their stored laps: one stint per stint number. */
export function actualStrategy(laps) {
  const byStint = new Map()
  for (const l of laps) {
    if (l.stint == null) continue
    const s = byStint.get(l.stint) ?? { stint: l.stint, compound: null, start: Infinity, end: -Infinity }
    if (s.compound == null && l.compound) s.compound = String(l.compound).toUpperCase()
    s.start = Math.min(s.start, l.lap_number)
    s.end = Math.max(s.end, l.lap_number)
    byStint.set(l.stint, s)
  }
  const stints = [...byStint.values()].sort((a, b) => a.stint - b.stint)
  const totalLaps = laps.length ? Math.max(...laps.map((l) => l.lap_number)) : 0
  return {
    stints, totalLaps,
    compounds: stints.map((s) => s.compound ?? 'MEDIUM'),
    pitLaps: stints.slice(0, -1).map((s) => s.end), // a stop happens at the end of each stint but the last
  }
}

/** Keep existing pit laps when the stop count changes; spread any new stops evenly over the race. */
export function resizePitLaps(existing, stops, totalLaps) {
  const kept = existing.slice(0, stops)
  const out = [...kept]
  for (let i = kept.length; i < stops; i++) {
    const guess = Math.round((totalLaps * (i + 1)) / (stops + 1)) || 10 * (i + 1)
    const prev = out.length ? Number(out[out.length - 1]) : 0
    out.push(String(Math.max(guess, prev + MIN_STINT)))
  }
  return out
}

/** Client-side sanity check only; the backend is authoritative. `totalLaps` is optional. */
export function validateInputs({ compounds, pitLaps, totalLaps }) {
  const errors = []
  if (compounds.length !== pitLaps.length + 1) errors.push('Need one more compound than pit laps.')
  if (pitLaps.some((p) => !Number.isInteger(p) || p < 1)) errors.push('Enter a whole lap number (1 or more) for every stop.')
  if (pitLaps.some((p, i) => i > 0 && p <= pitLaps[i - 1])) errors.push('Pit laps must be in increasing order.')
  if (new Set(compounds).size < 2) errors.push('Use at least two different compounds.')
  if (errors.length === 0) {
    if (totalLaps) {
      if (pitLaps.some((p) => p >= totalLaps)) errors.push(`Pit laps must be before the last lap (race is ${totalLaps} laps).`)
      const bounds = [0, ...pitLaps, totalLaps]
      if (bounds.some((b, i) => i > 0 && b - bounds[i - 1] < MIN_STINT)) errors.push(`Each stint must be at least ${MIN_STINT} laps.`)
    }
  }
  return errors
}

/** Say where the pit-loss figure came from, so a typical value is never mistaken for a measurement. */
export function pitLossNote(r) {
  if (r.pit_loss_seconds == null) return ''
  const v = `${r.pit_loss_seconds.toFixed(1)} s`
  if (r.pit_loss_source === 'measured') return `Pit loss used: ${v}, measured from ${r.pit_loss_stops} clean stops in this race.`
  if (r.pit_loss_source === 'default') return `Pit loss used: ${v}, a typical value (this race's stops could not be measured reliably).`
  return `Pit loss used: ${v}.`
}

const describeStints = (stints) => stints.map((s) => `${s.compound ?? 'unknown'} (laps ${s.start}–${s.end})`).join(' → ')

export default function StrategyLab() {
  const [sessionId, setSessionId] = useState('')
  const [driver, setDriver] = useState('')
  const [compounds, setCompounds] = useState(['MEDIUM', 'HARD'])
  const [pitLaps, setPitLaps] = useState(['22']) // strings: they are text inputs
  const run = useMutation({ mutationFn: api.simulateStrategy })
  const { year } = useSeason()
  const events = useQuery({ queryKey: ['events', year], queryFn: () => api.events(year), enabled: !!year })
  const drivers = useQuery({
    queryKey: ['drivers', sessionId], queryFn: () => api.sessionDrivers(sessionId), enabled: !!sessionId,
  })
  const laps = useQuery({
    queryKey: ['laps', sessionId, driver], queryFn: () => api.laps(sessionId, driver), enabled: !!sessionId && !!driver,
  })
  const races = (events.data ?? []).flatMap((e) =>
    e.sessions.filter((x) => x.type === 'R' && x.status === 'loaded').map((x) => ({ id: x.session_id, label: `R${e.round} ${e.name}` })),
  )

  const actual = laps.data ? actualStrategy(laps.data.laps) : null
  const totalLaps = actual?.totalLaps || undefined

  // Start the what-if from what the driver really did.
  const actualKey = actual ? `${sessionId}-${driver}` : null
  useEffect(() => {
    if (!actual || actual.compounds.length < 2) return
    setCompounds(actual.compounds)
    setPitLaps(actual.pitLaps.map(String))
    run.reset()
  }, [actualKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const pitNums = pitLaps.map((p) => (p === '' ? NaN : Number(p)))
  const errors = validateInputs({ compounds, pitLaps: pitNums, totalLaps })
  const stops = compounds.length - 1
  const compoundOptions = [...new Set([...COMPOUNDS, ...compounds])]

  const setStops = (n) => {
    setCompounds(Array.from({ length: n + 1 }, (_, i) => compounds[i] ?? COMPOUNDS[(i + 1) % COMPOUNDS.length]))
    setPitLaps(resizePitLaps(pitLaps, n, totalLaps ?? 0))
  }
  const resetToActual = () => {
    if (!actual) return
    setCompounds(actual.compounds)
    setPitLaps(actual.pitLaps.map(String))
    run.reset()
  }

  const submit = (e) => {
    e.preventDefault()
    if (errors.length) return
    run.mutate({
      session_id: Number(sessionId), driver_code: driver.toUpperCase(),
      stint_compounds: compounds, pit_laps: pitNums,
    })
  }
  const r = run.data

  return (
    <section>
      <PageHeader eyebrow="Strategy lab" title="What-if tyre strategy" />
      <p className="muted small lab-intro">
        Pick a race and driver, change the tyres or pit laps, and the model estimates how much faster or slower
        that plan would have been than what the driver actually did. It starts from the real strategy.
      </p>
      <form className="card form" onSubmit={submit}>
        <label>Race
          <select value={sessionId} onChange={(e) => { setSessionId(e.target.value); setDriver('') }} required>
            <option value="">Select…</option>
            {races.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
          </select>
        </label>
        <label>Driver
          <select value={driver} onChange={(e) => setDriver(e.target.value)} required disabled={!sessionId}>
            <option value="">Select…</option>
            {(drivers.data ?? []).map((d) => <option key={d.code} value={d.code}>{d.code} {d.name ? `(${d.name})` : ''}</option>)}
          </select>
        </label>

        {actual && actual.stints.length > 0 && (
          <div className="actual-box" aria-label="Actual strategy">
            <strong>Actual strategy</strong> ({actual.totalLaps} laps, {actual.stints.length - 1} stop{actual.stints.length === 2 ? '' : 's'}):
            <div>{describeStints(actual.stints)}</div>
            <button type="button" onClick={resetToActual}>Reset to actual</button>
          </div>
        )}

        <label>Number of pit stops
          <select value={stops} onChange={(e) => setStops(Number(e.target.value))}>
            {Array.from({ length: Math.max(MAX_STOPS, stops) }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>

        {compounds.map((c, i) => (
          <div className="pair" key={i}>
            <label>Stint {i + 1} tyre
              <select value={c} onChange={(e) => setCompounds(compounds.map((x, j) => (j === i ? e.target.value : x)))}>
                {compoundOptions.map((x) => <option key={x}>{x}</option>)}
              </select>
            </label>
            {i < stops ? (
              <label>Stop {i + 1} on lap
                <input type="number" min={1} max={totalLaps ? totalLaps - 1 : undefined} inputMode="numeric" value={pitLaps[i] ?? ''}
                  onChange={(e) => setPitLaps(pitLaps.map((x, j) => (j === i ? e.target.value : x)))} />
              </label>
            ) : (
              <div className="muted small pair-note">Runs to the flag{totalLaps ? ` (lap ${totalLaps})` : ''}</div>
            )}
          </div>
        ))}

        <p className="muted small">
          Rules: one tyre per stint and one lap number per stop, in order. Each stint must be at least {MIN_STINT} laps,
          and a dry race needs at least two different tyres.
        </p>
        {errors.map((m) => <p key={m} role="alert" className="error">{m}</p>)}
        <button type="submit" disabled={errors.length > 0 || run.isPending}>
          {run.isPending ? 'Simulating…' : 'Simulate'}
        </button>
      </form>

      {run.isError && <p role="alert" className="error">{run.error.message}</p>}
      {r && (
        <div className="card" aria-live="polite">
          <h2>Result</h2>
          {r.constraint_violations.length > 0 ? (
            <ul className="error">{r.constraint_violations.map((v) => <li key={v}>{v}</li>)}</ul>
          ) : (
            <>
              <StrategyResult result={r} />
              <p className="muted small">{pitLossNote(r)}</p>
            </>
          )}
          <ul className="muted small">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          <p className="muted small">Model {r.model_version}. Estimates only; not a prediction of the real outcome.</p>
        </div>
      )}
    </section>
  )
}
