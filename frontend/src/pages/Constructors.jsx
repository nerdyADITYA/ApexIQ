import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api.js'
import { useSeason } from '../hooks/useSeason.jsx'
import QueryState from '../components/common/QueryState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import TeamBarRow from '../components/cards/TeamBarRow.jsx'

export default function Constructors() {
  const { year } = useSeason()
  const standings = useQuery({ queryKey: ['standings', year], queryFn: () => api.standings(year), enabled: !!year })
  return (
    <section>
      <PageHeader eyebrow="Constructors" title={`${year ?? ''} standings`} />
      <QueryState query={standings} empty={(d) => !d.constructors.length}>
        {(d) => (
          <div className="card">
            <ul className="barlist">
              {d.constructors.map((r) => (
                <TeamBarRow
                  key={r.constructor} rank={r.position} team={r.constructor} label={r.constructor}
                  to={`/constructors/${encodeURIComponent(r.constructor)}`} value={r.points}
                  max={d.constructors[0].points}
                />
              ))}
            </ul>
          </div>
        )}
      </QueryState>
    </section>
  )
}
