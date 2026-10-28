import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import QueryState from '../components/common/QueryState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import TeamBarRow from '../components/cards/TeamBarRow.jsx'
import { shortTeam } from '../utils/teams.js'

export default function Drivers() {
  const { year } = useSeason()
  const standings = useQuery({ queryKey: ['standings', year], queryFn: () => api.standings(year), enabled: !!year })
  return (
    <section>
      <PageHeader eyebrow="Drivers" title={`${year ?? ''} standings`} />
      <QueryState query={standings} empty={(d) => !d.drivers.length}>
        {(d) => (
          <div className="card">
            <ul className="barlist">
              {d.drivers.map((r) => (
                <TeamBarRow
                  key={r.driver} rank={r.position} team={r.constructor} label={r.name ?? r.driver}
                  to={`/drivers/${r.driver}`} value={r.points} max={d.drivers[0].points}
                  sub={`${r.driver} · ${shortTeam(r.constructor)} · ${r.wins} ${r.wins === 1 ? 'win' : 'wins'}`}
                />
              ))}
            </ul>
          </div>
        )}
      </QueryState>
    </section>
  )
}
