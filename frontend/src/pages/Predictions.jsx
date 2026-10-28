import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import PageHeader, { Field } from '../components/layout/PageHeader.jsx'
import QueryState from '../components/common/QueryState.jsx'
import Kpi from '../components/cards/Kpi.jsx'
import TeamBarRow from '../components/cards/TeamBarRow.jsx'
import { TrackRecordView } from '../components/charts/TrackRecord.jsx'
import { shortTeam, teamColor } from '../utils/teams.js'

/** "<1%" instead of a misleading "0%" for small but non-zero probabilities. */
export function formatPct(p) {
  if (p == null) return '—'
  if (p === 0) return '0%'
  if (p < 0.01) return '<1%'
  return `${Math.round(p * 100)}%`
}

/** Labels for the forecast mode shown in the header tiles. */
export function modeInfo(mode) {
  return mode === 'post-qualifying'
    ? { label: 'Post-qualifying', sub: 'qualifying order used as the grid', model: 'Form + grid' }
    : { label: 'Pre-qualifying', sub: 'grid not known yet', model: 'Baseline' }
}

/** Heatmap cell colour: opacity follows probability (square-rooted so small values stay visible). */
export function heatColor(p) {
  const a = Math.min(1, Math.sqrt(Math.max(0, p)))
  return `rgba(77, 195, 255, ${a.toFixed(3)})`
}

/** The three best expected finishers, in order. */
export const podiumDrivers = (forecast) => [...forecast.drivers].sort((a, b) => a.predicted_rank - b.predicted_rank).slice(0, 3)

const fmtDate = (iso) => (iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }) : '')

function Heatmap({ drivers }) {
  const n = drivers[0]?.position_probs.length ?? 0
  return (
    <div className="scroll">
      <table className="heat" aria-label="Probability of each finishing position">
        <thead>
          <tr>
            <th scope="col">Driver</th>
            {Array.from({ length: n }, (_, k) => <th key={k} scope="col">P{k + 1}</th>)}
          </tr>
        </thead>
        <tbody>
          {drivers.map((d) => (
            <tr key={d.driver}>
              <th scope="row"><i className="heat-stripe" style={{ background: teamColor(d.team) }} aria-hidden="true" />{d.driver}</th>
              {d.position_probs.map((p, k) => (
                <td key={k} style={{ background: heatColor(p) }} title={`${d.driver} finishing P${k + 1}: ${formatPct(p)}`}
                  aria-label={`${d.driver} finishing P${k + 1}: ${formatPct(p)}`}>
                  {p >= 0.08 ? Math.round(p * 100) : ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Forecast({ forecast: f }) {
  const maxPts = Math.max(...f.constructors.map((c) => c.expected_points), 1)
  const mode = modeInfo(f.mode)
  const post = f.mode === 'post-qualifying'
  return (
    <>
      {!post && (
        <div className="banner note-top" role="note" data-testid="same-forecast-note">
          <strong className="banner-title"><Info size={15} aria-hidden="true" /> Why the upcoming races look alike</strong>
          <p>
            Before qualifying, every upcoming race gets the same forecast. They are built from the same results, and a
            circuit-specific effect was tested and did not predict better, so the model cannot tell circuits apart.
            Forecasts separate once a weekend's qualifying is ingested, because the grid differs.
          </p>
        </div>
      )}
      <section className="kpis" aria-label="Forecast status">
        <Kpi label="Forecast type" value={mode.label} sub={mode.sub} />
        <Kpi label="Based on" value={`Rounds 1–${f.as_of_round}`} sub={`${f.race.year} season so far`} />
        <Kpi label="Circuit history" value={f.race.circuit_history_seasons} sub={f.race.circuit_history_seasons === 1 ? 'past season in the data' : 'past seasons in the data'} />
        <Kpi label="Model" value={mode.model} sub={`${f.n_simulations.toLocaleString()} simulations`} />
      </section>

      <div className="podium" aria-label="Predicted podium">
        {podiumDrivers(f).map((d) => (
          <div key={d.driver} className="podium-card" style={{ borderTopColor: teamColor(d.team) }}>
            <div className="podium-rank">P{d.predicted_rank}</div>
            <div className="podium-name">{d.name ?? d.driver}</div>
            <div className="muted small">{d.driver} · {shortTeam(d.team)}</div>
            <div className="podium-stats">
              <span><b>{formatPct(d.p_win)}</b> win</span>
              <span><b>{formatPct(d.p_podium)}</b> podium</span>
            </div>
          </div>
        ))}
      </div>

      <div className="dash">
        <div className="card">
          <h2>Predicted classification</h2>
          <p className="muted small">Ordered by expected finishing position (a retirement counts as last). Not a single predicted result.</p>
          <div className="scroll">
            <table className="classification">
              <thead>
                <tr><th>#</th><th>Driver</th>{post && <th>Grid</th>}<th>Exp. pos</th><th>Win</th><th>Podium</th><th>Points</th><th>DNF</th><th>Exp. pts</th></tr>
              </thead>
              <tbody>
                {f.drivers.map((d) => (
                  <tr key={d.driver}>
                    <td>{d.predicted_rank}</td>
                    <td className="drivercell">
                      <i className="heat-stripe" style={{ background: teamColor(d.team) }} aria-hidden="true" />
                      <Link to={`/drivers/${d.driver}`}>{d.driver}</Link>
                      <span className="muted small"> {shortTeam(d.team)}</span>
                    </td>
                    {post && <td>{d.grid ?? '—'}</td>}
                    <td>{d.expected_position.toFixed(1)}</td>
                    <td>{formatPct(d.p_win)}</td><td>{formatPct(d.p_podium)}</td><td>{formatPct(d.p_points)}</td>
                    <td>{formatPct(d.p_dnf)}</td><td>{d.expected_points.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="dash-col">
          <div className="card">
            <h2>Constructors: expected points</h2>
            <ul className="barlist">
              {f.constructors.map((c, i) => (
                <TeamBarRow key={c.team} rank={i + 1} team={c.team} label={shortTeam(c.team)} to={`/constructors/${encodeURIComponent(c.team)}`}
                  value={c.expected_points} max={maxPts} valueText={c.expected_points.toFixed(1)} />
              ))}
            </ul>
          </div>
          <div className="card">
            <h2>Read this carefully</h2>
            <ul className="muted small notes">
              {f.caveats.map((c) => <li key={c}>{c}</li>)}
              {f.lineup_notes.map((n) => <li key={n.driver}>{n.note}</li>)}
            </ul>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Finishing position probabilities</h2>
        <p className="muted small">Each row is one driver; the number in a cell is the percent chance of finishing in that position (shown when 8% or more). Retirements are not in the grid, so a row adds up to 100% minus the DNF chance.</p>
        <Heatmap drivers={[...f.drivers].sort((a, b) => a.predicted_rank - b.predicted_rank)} />
      </div>
      <p className="muted small">Model {f.model_version}, generated {new Date(f.generated_at).toLocaleString()}. Probabilities are estimates, not guarantees and not betting advice.</p>
    </>
  )
}

/** Track record: fetches the chosen source and shows it. Saved-before-the-race forecasts first; the replay is opt-in. */
export function TrackRecord({ year }) {
  const [source, setSource] = useState('frozen')
  const q = useQuery({ queryKey: ['track-record', year, source], queryFn: () => api.trackRecord(year, source), enabled: !!year, retry: false })
  return (
    <div className="card">
      <h2>Track record</h2>
      <span className="segmented" role="group" aria-label="Track record source">
        <button type="button" aria-pressed={source === 'frozen'} onClick={() => setSource('frozen')}>Saved before the race</button>
        <button type="button" aria-pressed={source === 'replay'} onClick={() => setSource('replay')}>Retrospective replay</button>
      </span>
      <QueryState query={q}>{(data) => <TrackRecordView key={source} data={data} />}</QueryState>
    </div>
  )
}

export default function Predictions() {
  const { year } = useSeason()
  const list = useQuery({ queryKey: ['pred-upcoming', year], queryFn: () => api.predictionsUpcoming(year), enabled: !!year, retry: false })
  const [round, setRound] = useState(null)
  const upcoming = list.data?.upcoming ?? []

  useEffect(() => {
    if (upcoming.length && !upcoming.some((u) => u.round === round)) setRound(upcoming[0].round)
  }, [list.data]) // eslint-disable-line react-hooks/exhaustive-deps

  const forecast = useQuery({
    queryKey: ['pred-race', year, round], queryFn: () => api.raceForecast(year, round), enabled: !!year && round != null, retry: false,
  })
  const selected = upcoming.find((u) => u.round === round)

  return (
    <section>
      <PageHeader eyebrow="Race predictions" title={selected ? `${selected.event}${selected.date ? ` · ${fmtDate(selected.date)}` : ''}` : 'Upcoming races'}>
        {upcoming.length > 0 && (
          <Field label="Race">
            <select value={round ?? ''} onChange={(e) => setRound(Number(e.target.value))}>
              {upcoming.map((u) => <option key={u.round} value={u.round}>R{u.round} {u.event}{u.qualifying_available ? ' · grid set' : ''}</option>)}
            </select>
          </Field>
        )}
      </PageHeader>
      <QueryState query={list} empty={(d) => !d.upcoming.length}>
        {() => (
          <QueryState query={forecast}>{(f) => <Forecast forecast={f} />}</QueryState>
        )}
      </QueryState>
      {year && <TrackRecord year={year} />}
      {list.data && list.data.upcoming.length === 0 && <p className="muted">No upcoming races in {year}. Pick the current season in the selector.</p>}
    </section>
  )
}
