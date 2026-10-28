import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import QueryState from '../components/common/QueryState.jsx'
import { teamColor } from '../utils/teams.js'
import Stat from '../components/cards/Stat.jsx'
import StintTimeline from '../components/charts/StintTimeline.jsx'

const tip = { contentStyle: { background: '#1b1b22', border: '1px solid #444' } }
const fixed = (v, d = 1) => (v == null ? '—' : v.toFixed(d))

export default function DriverDetail() {
  const { code } = useParams()
  const { year } = useSeason()
  const profile = useQuery({
    queryKey: ['driver', code, year], queryFn: () => api.driverProfile(code, year), enabled: !!year, retry: false,
  })
  const tracks = useQuery({ queryKey: ['tracks', code], queryFn: () => api.driverTracks(code), retry: false })

  return (
    <section>
      <p><Link to="/drivers">← All drivers</Link></p>
      <QueryState query={profile}>
        {(p) => {
          const s = p.season_summary
          const color = teamColor(p.team)
          const rounds = p.rounds.map((r) => ({ ...r, label: `R${r.round}` }))
          const tm = p.teammate
          return (
            <>
              <PageHeader eyebrow={`${p.driver} · ${p.team} · ${p.season}`} title={p.name ?? p.driver}
                accent={teamColor(p.team)} />
              <div className="stats">
                <Stat label="Points" value={s.points} digits={0} />
                <Stat label="Wins" value={s.wins} />
                <Stat label="Podiums" value={s.podiums} />
                <Stat label="DNFs" value={s.dnfs} />
                <Stat label="Avg grid" value={s.avg_grid} />
                <Stat label="Avg finish" value={s.avg_finish} />
                <Stat label="Avg quali" value={p.qualifying.avg_position} hint={`${p.qualifying.sessions} qualifying sessions`} />
                <Stat
                  label="Pace vs field" value={p.pace.median_delta_pct_vs_field} unit="%" digits={2}
                  hint="Median of per-race % delta to the field's median clean pace. Negative = faster."
                />
              </div>

              <div className="grid">
                <div className="card">
                  <h2>Points progression</h2>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={rounds}>
                      <CartesianGrid stroke="#333" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#aaa" /><YAxis stroke="#aaa" /><Tooltip {...tip} />
                      <Line isAnimationActive={false} dataKey="cumulative_points" name="Points" stroke={color} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="card">
                  <h2>Race pace vs field (%)</h2>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={rounds}>
                      <CartesianGrid stroke="#333" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#aaa" /><YAxis stroke="#aaa" reversed /><Tooltip {...tip} />
                      <ReferenceLine y={0} stroke="#aaa" />
                      <Bar isAnimationActive={false} dataKey="pace_delta_pct" name="% vs field (negative = faster)" fill={color} />
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="muted small">
                    Axis reversed: a taller bar means faster. {p.pace.rated_races} races rated
                    (at least {p.pace.min_clean_laps_per_race} clean laps).
                  </p>
                </div>
              </div>

              <div className="card">
                <h2>Teammate: {tm.name ?? '—'}</h2>
                <div className="stats">
                  <Stat label="Median pace gap" value={tm.median_gap_pct} unit="%" digits={2} hint="Negative = faster than teammate" />
                  <Stat label="Faster in races" value={tm.faster_in_races} hint={`of ${tm.rated_races} rated`} />
                  <Stat label="Sector 1 gap" value={tm.sector_median_gap_s?.s1_s} unit=" s" digits={3} />
                  <Stat label="Sector 2 gap" value={tm.sector_median_gap_s?.s2_s} unit=" s" digits={3} />
                  <Stat label="Sector 3 gap" value={tm.sector_median_gap_s?.s3_s} unit=" s" digits={3} />
                </div>
                <p className="muted small">
                  Negative = faster than teammate. Median over {tm.rated_races} races where both were rated.
                </p>
              </div>

              <div className="card">
                <h2>Race by race</h2>
                <div className="scroll">
                  <table>
                    <thead>
                      <tr><th>Rd</th><th>Event</th><th>Grid</th><th>Finish</th><th>Pts</th><th>Pace %</th><th>Tyres</th></tr>
                    </thead>
                    <tbody>
                      {p.rounds.map((r) => (
                        <tr key={r.round}>
                          <td>{r.round}</td><td>{r.event.replace(' Grand Prix', '')}</td><td>{r.grid ?? '—'}</td>
                          <td>{r.dnf ? `DNF (${r.status})` : r.finish ?? '—'}</td><td>{r.points}</td>
                          <td>{fixed(r.pace_delta_pct, 2)}</td>
                          <td className="stint-cell"><StintTimeline stints={r.stints} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted small">Tyres: S soft, M medium, H hard; bar length is proportional to laps.</p>
              </div>
              <ul className="muted small">{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </>
          )
        }}
      </QueryState>

      <QueryState query={tracks}>
        {(t) => (
          <div className="card">
            <h2>By circuit (all ingested seasons)</h2>
            <div className="scroll">
              <table>
                <thead>
                  <tr><th>Circuit</th><th>Seasons</th><th>Starts</th><th>Avg grid</th><th>Avg finish</th><th>Best</th><th>DNFs</th></tr>
                </thead>
                <tbody>
                  {t.circuits.map((c) => (
                    <tr key={c.circuit}>
                      <td>{c.circuit}</td><td>{c.seasons.join(', ')}</td><td>{c.starts}</td>
                      <td>{fixed(c.avg_grid)}</td><td>{fixed(c.avg_finish)}</td>
                      <td>{c.best_finish ?? '—'}</td><td>{c.dnfs}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="muted small">{t.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          </div>
        )}
      </QueryState>
    </section>
  )
}
