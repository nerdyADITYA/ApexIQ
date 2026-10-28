import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import QueryState from '../components/common/QueryState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Kpi from '../components/cards/Kpi.jsx'
import TeamBarRow from '../components/cards/TeamBarRow.jsx'
import { shortTeam, teamColor } from '../utils/teams.js'

const POINTS_PER_WIN = 25

/** "≈100%" instead of a misleading exact 100 for model estimates. */
export function formatOdds(p) {
  if (p == null) return null
  if (p >= 0.995) return '≈100%'
  if (p < 0.005) return '<1%'
  return `${Math.round(p * 100)}%`
}

/** Pivot the progression series into one row per round for Recharts. */
export function progressionRows(prog) {
  return prog.rounds.map((round, i) => ({
    round, ...Object.fromEntries(prog.series.map((s) => [s.driver, s.points[i]])),
  }))
}

/** A second driver from the same team gets a dashed line so teammates stay distinguishable. */
export function lineStyles(series) {
  const seen = {}
  return series.map((s) => {
    seen[s.team] = (seen[s.team] ?? 0) + 1
    return { driver: s.driver, color: teamColor(s.team), dash: seen[s.team] > 1 ? '5 3' : undefined }
  })
}

export default function Dashboard() {
  const { year } = useSeason()
  const on = { enabled: !!year }
  const standings = useQuery({ queryKey: ['standings', year], queryFn: () => api.standings(year), ...on })
  const forecast = useQuery({ queryKey: ['forecast', year], queryFn: () => api.driverForecast(year), retry: false, ...on })
  const progression = useQuery({ queryKey: ['progression', year], queryFn: () => api.progression(year), retry: false, ...on })
  const events = useQuery({ queryKey: ['events', year], queryFn: () => api.events(year), ...on })

  if (!year) {
    return (
      <>
        <PageHeader eyebrow="Season overview" title="No season yet" />
        <p className="muted">No seasons ingested yet. Run an ingestion script first.</p>
      </>
    )
  }

  const lastRound = progression.data?.rounds.at(-1)
  const total = events.data?.length
  const title = `${year}${lastRound ? ` · Round ${lastRound}${total ? ` of ${total}` : ''}` : ''}`

  return (
    <>
      <PageHeader eyebrow="Season overview" title={title} />
      <QueryState query={standings} empty={(d) => !d.drivers.length}>
        {(d) => {
          const [first, second] = d.drivers
          const remaining = forecast.data?.races_remaining ?? (total && lastRound ? total - lastRound : null)
          const leaderOdds = forecast.data?.drivers.find((x) => x.driver === first.driver)?.win_probability
          const maxDriver = first.points
          const maxTeam = d.constructors[0]?.points ?? 1
          return (
            <>
              <section className="kpis" aria-label="Season headlines">
                <Kpi label="Leader" value={first.driver} sub={`${first.points} pts · ${shortTeam(first.constructor)}`}
                  accent={teamColor(first.constructor)} />
                <Kpi label="Lead over P2" value={second ? `+${first.points - second.points}` : null}
                  sub={second ? `${second.driver}, ${second.points} pts` : undefined} />
                <Kpi label="Races left" value={remaining}
                  sub={remaining == null ? undefined : remaining === 0 ? 'season complete'
                    : `${remaining * POINTS_PER_WIN} pts in GPs, sprints extra`} />
                <Kpi label="Title odds" value={formatOdds(leaderOdds)}
                  sub={leaderOdds == null ? 'forecast unavailable' : `${first.driver}, model estimate`} />
              </section>

              <div className="dash">
                <div className="card">
                  <h2>Drivers</h2>
                  <ul className="barlist">
                    {d.drivers.map((r) => (
                      <TeamBarRow key={r.driver} rank={r.position} team={r.constructor} label={r.driver}
                        to={`/drivers/${r.driver}`} value={r.points} max={maxDriver} sub={r.name} />
                    ))}
                  </ul>
                </div>
                <div className="dash-col">
                  <div className="card">
                    <h2>Constructors</h2>
                    <ul className="barlist">
                      {d.constructors.map((r) => (
                        <TeamBarRow key={r.constructor} rank={r.position} team={r.constructor}
                          label={shortTeam(r.constructor)} to={`/constructors/${encodeURIComponent(r.constructor)}`}
                          value={r.points} max={maxTeam} />
                      ))}
                    </ul>
                  </div>
                  <div className="card">
                    <h2>Points progression</h2>
                    <QueryState query={progression}>
                      {(p) => {
                        const styles = lineStyles(p.series)
                        return (
                          <ResponsiveContainer width="100%" height={240}>
                            <LineChart data={progressionRows(p)}>
                              <CartesianGrid stroke="#262a33" strokeDasharray="3 3" />
                              <XAxis dataKey="round" stroke="#7c8594" tickFormatter={(v) => `R${v}`} />
                              <YAxis stroke="#7c8594" width={44} />
                              <Tooltip contentStyle={{ background: '#1c2028', border: '1px solid #2f343d' }}
                                labelFormatter={(v) => `After round ${v}`} />
                              <Legend />
                              {styles.map((s) => (
                                <Line key={s.driver} dataKey={s.driver} stroke={s.color} strokeDasharray={s.dash}
                                  dot={false} strokeWidth={2} isAnimationActive={false} />
                              ))}
                            </LineChart>
                          </ResponsiveContainer>
                        )
                      }}
                    </QueryState>
                    <p className="muted small">Cumulative points (race and sprint) for the current top six. Dashed: a team's second driver.</p>
                  </div>
                </div>
              </div>
              {forecast.data && (
                <p className="muted small">
                  Forecast {forecast.data.model_version}: {forecast.data.n_simulations} simulations, generated{' '}
                  {forecast.data.generated_at}. Probabilities are model estimates, not guarantees.
                </p>
              )}
              {forecast.isError && <p className="muted small">Forecast unavailable: {forecast.error.message}</p>}
            </>
          )
        }}
      </QueryState>
    </>
  )
}
