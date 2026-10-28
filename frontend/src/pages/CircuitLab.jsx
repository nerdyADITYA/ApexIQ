import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api.js'
import PageHeader from '../components/layout/PageHeader.jsx'
import { sessionName } from '../utils/sessions.js'
import QueryState from '../components/common/QueryState.jsx'
import ErrorBoundary from '../components/common/ErrorBoundary.jsx'
import CircuitScene, { COLOR_A, COLOR_B } from '../three/CircuitScene.jsx'
import { PlaybackControls, usePlayback } from '../three/TelemetryPlayback.jsx'
import TelemetryCharts from '../three/TelemetryCharts.jsx'
import LapComparison from '../three/LapComparison.jsx'
import { lapDuration, speedColor, stateAt } from '../utils/telemetry.js'

function SpeedLegend({ range }) {
  const stops = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const [r, g, b] = speedColor(range[0] + f * (range[1] - range[0]), range[0], range[1])
    return `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`
  })
  return (
    <div className="legend" aria-label="Track colour legend: speed">
      <span>{Math.round(range[0])} km/h</span>
      <div className="legend-bar" style={{ background: `linear-gradient(90deg, ${stops.join(',')})` }} />
      <span>{Math.round(range[1])} km/h</span>
    </div>
  )
}

function Lab({ data }) {
  const [colorBySpeed, setColorBySpeed] = useState(true)
  const [showCorners, setShowCorners] = useState(false)
  const [cameraPreset, setCameraPreset] = useState('angled')

  const duration = Math.max(lapDuration(data.samples.a), data.samples.b ? lapDuration(data.samples.b) : 0)
  const playback = usePlayback(duration)
  const speeds = data.samples.a.speed_kph.filter((v) => v != null)
  const speedRange = useMemo(() => [Math.min(...speeds), Math.max(...speeds)], [data]) // eslint-disable-line react-hooks/exhaustive-deps
  const cursor = stateAt(data.samples.a, data.samples.distance_m, playback.displayTime).distance

  return (
    <>
      <div className="lab">
      <div className="lab-main">
      {data.has_position ? (
        <div className="card scene-card">
          <div className="scene-toolbar">
            <label><input type="checkbox" checked={colorBySpeed} onChange={(e) => setColorBySpeed(e.target.checked)} /> Colour track by speed (driver A)</label>
            <label><input type="checkbox" checked={showCorners} onChange={(e) => setShowCorners(e.target.checked)} /> Speed-minimum markers</label>
            <span className="segmented" role="group" aria-label="Camera">
              <button type="button" aria-pressed={cameraPreset === 'angled'} onClick={() => setCameraPreset('angled')}>Angled</button>
              <button type="button" aria-pressed={cameraPreset === 'top'} onClick={() => setCameraPreset('top')}>Top</button>
            </span>
          </div>
          <div className="scene">
            <ErrorBoundary message="The 3D view could not start (WebGL may be unavailable). Telemetry charts below still work.">
              <CircuitScene data={data} playback={playback} colorBySpeed={colorBySpeed}
                showCorners={showCorners} cameraPreset={cameraPreset} speedRange={speedRange} />
            </ErrorBoundary>
          </div>
          {colorBySpeed && <SpeedLegend range={speedRange} />}
          <PlaybackControls playback={playback} />
          <p className="muted small">
            Mouse: drag to orbit, wheel to zoom, right-drag to pan. Touch: swipe sideways to rotate, pinch to zoom,
            two fingers to pan; swipe vertically to scroll the page.
          </p>
        </div>
      ) : (
        <div className="card" role="status">
          <strong>No position data for this lap, so the 3D track cannot be drawn.</strong>
          <p className="muted small">Speed, throttle and brake traces are still available below.</p>
        </div>
      )}
      </div>
      <div className="lab-side">
      <LapComparison data={data} time={playback.displayTime} colors={{ a: COLOR_A, b: COLOR_B }} />
      </div>
      </div>
      <TelemetryCharts data={data} cursorDistance={cursor} />
      <ul className="muted small">{data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </>
  )
}

export default function CircuitLab() {
  const sessions = useQuery({ queryKey: ['tel-sessions'], queryFn: api.telemetrySessions })
  const [sessionId, setSessionId] = useState('')
  const [a, setA] = useState('')
  const [b, setB] = useState('')

  const session = (sessions.data ?? []).find((s) => String(s.session_id) === String(sessionId))

  useEffect(() => {
    if (!sessionId && sessions.data?.length) setSessionId(String(sessions.data[0].session_id))
  }, [sessions.data, sessionId])

  useEffect(() => {
    if (session) {
      setA(session.drivers[0]?.code ?? '')
      setB(session.drivers[1]?.code ?? '')
    }
  }, [session?.session_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const lap = useQuery({
    queryKey: ['lap-comparison', sessionId, a, b],
    queryFn: () => api.lapComparison(sessionId, a, b || undefined),
    enabled: !!sessionId && !!a, retry: false,
  })

  return (
    <section>
      <PageHeader eyebrow="Circuit lab" title="Telemetry lap replay" noSeason />
      <p className="muted small">
        Replay of each driver's fastest recorded lap in a session, drawn on a track reconstructed from telemetry.
        This is a telemetry replay, not a physics simulation.
      </p>
      <QueryState query={sessions} empty={(d) => !d.length}>
        {(list) => (
          <form className="card lab-form" onSubmit={(e) => e.preventDefault()}>
            <label>Session
              <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                {list.map((s) => (
                  <option key={s.session_id} value={s.session_id}>{s.year} R{s.round} {s.event} · {sessionName(s.type)}</option>
                ))}
              </select>
            </label>
            <label>Driver A
              <select value={a} onChange={(e) => setA(e.target.value)}>
                {session?.drivers.map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
              </select>
            </label>
            <label>Driver B
              <select value={b} onChange={(e) => setB(e.target.value)}>
                <option value="">None</option>
                {session?.drivers.filter((d) => d.code !== a).map((d) => <option key={d.code} value={d.code}>{d.code}</option>)}
              </select>
            </label>
          </form>
        )}
      </QueryState>
      {sessionId && a && (
        <QueryState query={lap}>{(data) => <Lab key={`${sessionId}-${a}-${b}`} data={data} />}</QueryState>
      )}
    </section>
  )
}
