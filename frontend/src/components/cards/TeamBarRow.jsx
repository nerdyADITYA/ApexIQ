import { Link } from 'react-router-dom'
import { teamColor } from '../../utils/teams.js'

/**
 * One standings row: rank, team-colour stripe, label, proportional bar, value.
 * `max` is the value that fills the bar (usually the leader's points).
 */
export default function TeamBarRow({ rank, team, label, to, value, max, sub, valueText }) {
  const color = teamColor(team)
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  const name = to ? <Link to={to}>{label}</Link> : label
  return (
    <li className="barrow">
      <span className="barrow-rank">{rank}</span>
      <span className="barrow-stripe" style={{ background: color }} aria-hidden="true" />
      <span className="barrow-label">
        <b>{name}</b>
        {sub && <small>{sub}</small>}
      </span>
      <span className="barrow-track" role="meter" aria-label={`${label} points`} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
        <i style={{ width: `${pct}%`, background: color }} />
      </span>
      <span className="barrow-value">{valueText ?? value}</span>
    </li>
  )
}
