import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { formatOdds, lineStyles, progressionRows } from './Dashboard.jsx'
import Kpi from '../components/cards/Kpi.jsx'
import TeamBarRow from '../components/cards/TeamBarRow.jsx'
import { FALLBACK_COLOR, shortTeam, teamColor } from '../utils/teams.js'

describe('team colours', () => {
  it('maps known teams, falls back for unknown, and shortens labels', () => {
    expect(teamColor('Mercedes')).toBe('#27F4D2')
    expect(teamColor('Some New Team')).toBe(FALLBACK_COLOR)
    expect(teamColor(null)).toBe(FALLBACK_COLOR)
    expect(shortTeam('Red Bull Racing')).toBe('Red Bull')
    expect(shortTeam('Haas F1 Team')).toBe('Haas')
    expect(shortTeam(null)).toBe('—')
  })
})

describe('formatOdds', () => {
  it('avoids claiming exact certainty and handles missing values', () => {
    expect(formatOdds(1)).toBe('≈100%')
    expect(formatOdds(0.9961)).toBe('≈100%')
    expect(formatOdds(0.0004)).toBe('<1%')
    expect(formatOdds(0.4249)).toBe('42%')
    expect(formatOdds(null)).toBeNull()
  })
})

describe('progression helpers', () => {
  const prog = {
    rounds: [1, 2],
    series: [
      { driver: 'ANT', team: 'Mercedes', points: [25, 50] },
      { driver: 'RUS', team: 'Mercedes', points: [18, 40] },
      { driver: 'LEC', team: 'Ferrari', points: [15, 33] },
    ],
  }
  it('pivots series into one row per round', () => {
    expect(progressionRows(prog)).toEqual([
      { round: 1, ANT: 25, RUS: 18, LEC: 15 },
      { round: 2, ANT: 50, RUS: 40, LEC: 33 },
    ])
  })
  it('dashes only the second driver of a team and colours by team', () => {
    const s = lineStyles(prog.series)
    expect(s.map((x) => x.dash)).toEqual([undefined, '5 3', undefined])
    expect(s[0].color).toBe(s[1].color)
    expect(s[2].color).toBe('#E8002D')
  })
})

describe('Kpi', () => {
  it('shows an em dash for a missing value and the sub text', () => {
    render(<Kpi label="Races left" value={null} sub="unknown" />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('unknown')).toBeInTheDocument()
  })
})

describe('TeamBarRow', () => {
  const row = (props) => render(
    <MemoryRouter><ul><TeamBarRow rank={1} team="Ferrari" label="LEC" value={50} max={100} {...props} /></ul></MemoryRouter>,
  )
  it('sizes the bar proportionally and exposes it as a labelled meter', () => {
    row({})
    const meter = screen.getByRole('meter', { name: 'LEC points' })
    expect(meter).toHaveAttribute('aria-valuenow', '50')
    expect(meter.firstChild.style.width).toBe('50%')
    expect(meter.firstChild.style.background).toMatch(/rgb\(232, 0, 45\)|#e8002d/i)
  })
  it('clamps the bar and tolerates a zero maximum; renders a link when given a target', () => {
    row({ value: 500, max: 100, to: '/drivers/LEC', sub: 'Ferrari' })
    expect(screen.getByRole('meter').firstChild.style.width).toBe('100%')
    expect(screen.getByRole('link', { name: 'LEC' })).toHaveAttribute('href', '/drivers/LEC')
  })
  it('does not divide by zero', () => {
    row({ value: 0, max: 0 })
    expect(screen.getByRole('meter').firstChild.style.width).toBe('0%')
  })
})

import { sessionName } from '../utils/sessions.js'

describe('sessionName', () => {
  it('expands every session code and passes unknown codes through', () => {
    expect(sessionName('SQ')).toBe('Sprint qualifying')
    expect(sessionName('SS')).toBe('Sprint shootout')
    expect(sessionName('R')).toBe('Race')
    expect(sessionName('Q')).toBe('Qualifying')
    expect(sessionName('S')).toBe('Sprint')
    expect(sessionName('XYZ')).toBe('XYZ')
  })
})


import { Forecast } from './Predictions.jsx'

describe('Forecast view modes', () => {
  const driver = (code, rank, grid) => ({
    driver: code, name: `Driver ${code}`, team: 'Mercedes', grid, predicted_rank: rank, expected_position: rank,
    expected_points: 10 - rank, p_win: rank === 1 ? 0.5 : 0.1, p_podium: 0.4, p_points: 0.8, p_dnf: 0.1,
    position_probs: [0.5, 0.3, 0.2], has_history: true,
  })
  const make = (mode, grid) => ({
    mode, model_version: 'v', generated_at: '2026-10-28T10:00:00Z', as_of_round: 18, n_simulations: 20000,
    race: { year: 2026, round: 19, event: 'Mexico City Grand Prix', circuit_history_seasons: 3 },
    drivers: [driver('AAA', 1, grid && 1), driver('BBB', 2, grid && 2), driver('CCC', 3, grid && 3)],
    constructors: [{ team: 'Mercedes', expected_points: 12 }], caveats: ['A caveat'], lineup_notes: [], positions: 3,
  })
  const show = (f) => render(<MemoryRouter><Forecast forecast={f} /></MemoryRouter>)

  it('pre-qualifying: no grid column, says the grid is unknown', () => {
    show(make('pre-qualifying', false))
    expect(screen.queryByRole('columnheader', { name: 'Grid' })).toBeNull()
    expect(screen.getByText('Pre-qualifying')).toBeInTheDocument()
    expect(screen.getByText('grid not known yet')).toBeInTheDocument()
  })
  it('post-qualifying: shows the grid column with the start positions', () => {
    show(make('post-qualifying', true))
    expect(screen.getByRole('columnheader', { name: 'Grid' })).toBeInTheDocument()
    expect(screen.getByText('Post-qualifying')).toBeInTheDocument()
    expect(screen.getByText('Form + grid')).toBeInTheDocument()
    const rows = screen.getAllByRole('row').filter((r) => r.textContent.includes('AAA'))
    expect(rows[0].textContent).toMatch(/AAA.*1.*1\.0/)
  })
  it('always renders the podium, the position grid and the caveats', () => {
    show(make('pre-qualifying', false))
    expect(screen.getByLabelText('Predicted podium')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Probability of each finishing position' })).toBeInTheDocument()
    expect(screen.getByText('A caveat')).toBeInTheDocument()
  })
})

describe('Forecast: explaining identical pre-qualifying forecasts', () => {
  const f = (mode) => ({
    mode, model_version: 'v', generated_at: '2026-10-28T10:00:00Z', as_of_round: 18, n_simulations: 20000,
    race: { year: 2026, round: 19, event: 'Mexico City Grand Prix', circuit_history_seasons: 3 },
    drivers: [{ driver: 'AAA', name: 'A', team: 'Mercedes', grid: mode === 'post-qualifying' ? 1 : null, predicted_rank: 1, expected_position: 1,
      expected_points: 10, p_win: 0.5, p_podium: 0.9, p_points: 1, p_dnf: 0.1, position_probs: [0.9], has_history: true }],
    constructors: [{ team: 'Mercedes', expected_points: 10 }], caveats: [], lineup_notes: [], positions: 1,
  })
  it('pre-qualifying says that all upcoming races share a forecast and why; post-qualifying does not', () => {
    const { unmount } = render(<MemoryRouter><Forecast forecast={f('pre-qualifying')} /></MemoryRouter>)
    expect(screen.getByTestId('same-forecast-note')).toHaveTextContent('every upcoming race gets the same forecast')
    expect(screen.getByTestId('same-forecast-note')).toHaveTextContent('did not predict better')
    unmount()
    render(<MemoryRouter><Forecast forecast={f('post-qualifying')} /></MemoryRouter>)
    expect(screen.queryByTestId('same-forecast-note')).toBeNull()
  })
})
