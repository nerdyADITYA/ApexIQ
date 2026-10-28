import { useState } from 'react'
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import Kpi from '../cards/Kpi.jsx'

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const MODE_LABEL = { 'pre-qualifying': 'Pre-qualifying', 'post-qualifying': 'Post-qualifying' }
const TARGET_LABEL = { win: 'Win', podium: 'Podium', points: 'Top 10' }

/** Mark which predicted drivers really made the actual top three. */
export function hitFlags(predicted, actual) {
  return predicted.map((code) => ({ code, hit: actual.includes(code) }))
}

/** Calibration bins -> chart points: x = forecast probability, y = how often it happened, n = cases behind it. */
export function calibrationPoints(bins) {
  return (bins ?? []).map((b) => ({ x: b.mean_predicted, y: b.observed_rate, n: b.n }))
}

/** One-line plain-language reading of a mode's summary. */
export function summaryLines(s) {
  if (!s || !s.races) return []
  return [
    `${s.winner_in_predicted_top3} of ${s.winners_scored} winners were in the predicted top three`,
    s.mean_p_win_given_to_winner == null ? null
      : `the winner was given ${pct(s.mean_p_win_given_to_winner)} on average (${pct(s.mean_chance_level_p_win)} by pure chance)`,
  ].filter(Boolean)
}

/** Presentational view of one track-record response (no fetching), so it can be tested directly. */
export function TrackRecordView({ data }) {
  const [mode, setMode] = useState(null)
  const [target, setTarget] = useState('podium')
  const modes = data.modes ?? []
  const active = mode && modes.includes(mode) ? mode : modes.includes('post-qualifying') ? 'post-qualifying' : modes[0]
  const s = data.summary?.[active]
  const rows = data.races.filter((r) => r.mode === active)
  const isReplay = data.source === 'replay'
  const points = calibrationPoints(data.calibration?.[active]?.[target])

  return (
    <div className="trackrec">
      <p className={isReplay ? 'banner warn' : 'banner'} role="note">{data.note}</p>

      {data.pending?.length > 0 && (
        <div className="pending" aria-label="Saved forecasts waiting for their race">
          <strong>{data.pending.length} saved forecast{data.pending.length === 1 ? '' : 's'} waiting for the race to be run:</strong>
          <ul>
            {data.pending.map((p) => (
              <li key={`${p.round}-${p.mode}`}>
                R{p.round} {p.event} <span className="muted">({MODE_LABEL[p.mode] ?? p.mode}, saved {new Date(p.saved_at).toLocaleString()})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.races.length === 0 ? (
        <p className="muted">
          {isReplay ? 'No past races to replay yet.' : 'No saved forecast has been scored yet. A forecast is scored after its race has been run and ingested.'}
        </p>
      ) : (
        <>
          {modes.length > 1 && (
            <span className="segmented" role="group" aria-label="Forecast type">
              {modes.map((m) => (
                <button key={m} type="button" aria-pressed={active === m} onClick={() => setMode(m)}>{MODE_LABEL[m] ?? m}</button>
              ))}
            </span>
          )}
          <section className="kpis" aria-label="Track record summary">
            <Kpi label="Races scored" value={s.races} sub={MODE_LABEL[active]} />
            <Kpi label="Winner in top 3" value={`${s.winner_in_predicted_top3} of ${s.winners_scored}`} sub={`predicted first in ${s.winner_predicted_first}`} />
            <Kpi label="Chance given to winner" value={pct(s.mean_p_win_given_to_winner)} sub={`${pct(s.mean_chance_level_p_win)} by pure chance`} />
            <Kpi label="Order accuracy" value={s.mean_spearman.toFixed(2)} sub={`rank correlation · ${s.mean_position_error.toFixed(1)} places off on average`} />
          </section>

          <div className="scroll">
            <table className="trtable">
              <thead>
                <tr><th>Rd</th><th>Race</th><th>Winner</th><th>Predicted podium</th><th>Actual podium</th><th>Rank corr.</th><th>Places off</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.round}-${r.mode}`}>
                    <td>{r.round}</td><td>{(r.event ?? '').replace(' Grand Prix', '')}</td>
                    <td>{r.winner} <span className="muted small">{pct(r.winner_p_win)}</span></td>
                    <td>{hitFlags(r.predicted_top3, r.actual_top3).map((h) => (
                      <span key={h.code} className={h.hit ? 'hit' : 'miss'} title={h.hit ? 'finished on the podium' : 'did not finish on the podium'}>{h.code}{h.hit ? ' ✓' : ''} </span>
                    ))}</td>
                    <td>{r.actual_top3.join(' ')}</td>
                    <td>{r.spearman.toFixed(2)}</td><td>{r.mean_position_error.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>Do the percentages mean what they say?</h3>
          <p className="muted small">
            Each dot groups forecasts of similar probability. On the diagonal, a 30% forecast happened about 30% of the time.
            Dot size is the number of cases; small dots are noisy.
          </p>
          <span className="segmented" role="group" aria-label="Calibration target">
            {Object.entries(TARGET_LABEL).map(([k, label]) => (
              <button key={k} type="button" aria-pressed={target === k} onClick={() => setTarget(k)}>{label}</button>
            ))}
          </span>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
              <CartesianGrid stroke="#262a33" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="x" domain={[0, 1]} tickFormatter={pct} stroke="#7c8594" name="Forecast"
                label={{ value: 'forecast probability', position: 'insideBottom', offset: -10, fill: '#7c8594', fontSize: 12 }} />
              <YAxis type="number" dataKey="y" domain={[0, 1]} tickFormatter={pct} stroke="#7c8594" width={46} name="Observed" />
              <ZAxis type="number" dataKey="n" range={[40, 260]} name="Cases" />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#aab2c0" strokeDasharray="4 4" />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: '#1c2028', border: '1px solid #2f343d' }}
                formatter={(v, name) => (name === 'Cases' ? v : pct(v))} />
              <Scatter data={points} fill="#4dc3ff" line={{ stroke: '#4dc3ff', strokeOpacity: 0.4 }} isAnimationActive={false} />
            </ScatterChart>
          </ResponsiveContainer>
          <ul className="muted small">{summaryLines(s).map((l) => <li key={l}>{l}</li>)}</ul>
        </>
      )}
    </div>
  )
}
