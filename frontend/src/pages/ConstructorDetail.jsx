import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import QueryState from '../components/common/QueryState.jsx'
import { teamColor } from '../utils/teams.js'
import Stat from '../components/cards/Stat.jsx'

const tip = { contentStyle: { background: '#1b1b22', border: '1px solid #444' } }

export default function ConstructorDetail() {
  const { team } = useParams()
  const { year } = useSeason()
  const q = useQuery({
    queryKey: ['constructor', team, year], queryFn: () => api.constructorProfile(team, year),
    enabled: !!year, retry: false,
  })
  return (
    <section>
      <p><Link to="/constructors">← All constructors</Link></p>
      <QueryState query={q}>
        {(c) => {
          const s = c.season_summary
          const color = teamColor(c.team)
          const rounds = c.by_round.map((r) => ({ ...r, label: `R${r.round}` }))
          return (
            <>
              <PageHeader eyebrow={`Constructor · ${c.season}`} title={c.team} accent={teamColor(c.team)} />
              <div className="stats">
                <Stat label="Points" value={s.points} digits={0} />
                <Stat label="Points / race" value={s.points_per_race} />
                <Stat label="Wins" value={s.wins} />
                <Stat label="Podiums" value={s.podiums} />
                <Stat label="Retirements" value={s.dnfs} hint={`of ${s.classified_starts} car starts`} />
                <Stat label="Retirement rate" value={s.retirement_rate == null ? null : s.retirement_rate * 100} unit="%" />
                <Stat label="Avg quali" value={c.qualifying.avg_position} />
                <Stat label="Pace vs field" value={c.pace.median_delta_pct_vs_field} unit="%" digits={2} hint="Negative = faster" />
                <Stat label="Median pit-lane time" value={c.pit_stops.median_pit_lane_time_s} unit=" s" hint={`${c.pit_stops.stops_measured} stops`} />
              </div>
              <div className="grid">
                <div className="card">
                  <h2>Points per round</h2>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={rounds}>
                      <CartesianGrid stroke="#333" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#aaa" /><YAxis stroke="#aaa" /><Tooltip {...tip} />
                      <Bar isAnimationActive={false} dataKey="points" name="Points" fill={color} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="card">
                  <h2>Cumulative points</h2>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={rounds}>
                      <CartesianGrid stroke="#333" strokeDasharray="3 3" />
                      <XAxis dataKey="label" stroke="#aaa" /><YAxis stroke="#aaa" /><Tooltip {...tip} />
                      <Line isAnimationActive={false} dataKey="cumulative_points" name="Points" stroke={color} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="card">
                <h2>Driver contribution</h2>
                <div className="scroll"><table>
                  <thead><tr><th>Driver</th><th>Points</th><th>Share</th><th>Races</th></tr></thead>
                  <tbody>
                    {c.driver_contribution.map((d) => (
                      <tr key={d.driver}>
                        <td><Link to={`/drivers/${d.driver}`}>{d.driver}</Link></td><td>{d.points}</td>
                        <td>{d.share == null ? '—' : `${(d.share * 100).toFixed(1)}%`}</td><td>{d.races}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              </div>
              <ul className="muted small">
                {c.notes.map((n) => <li key={n}>{n}</li>)}
                <li>{c.pit_stops.note}</li>
              </ul>
            </>
          )
        }}
      </QueryState>
    </section>
  )
}
