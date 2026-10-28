import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TrackRecordView, calibrationPoints, hitFlags, summaryLines } from './TrackRecord.jsx'

describe('track record helpers', () => {
  it('marks predicted drivers that really made the podium', () => {
    expect(hitFlags(['A', 'B', 'C'], ['B', 'C', 'D'])).toEqual([
      { code: 'A', hit: false }, { code: 'B', hit: true }, { code: 'C', hit: true }])
    expect(hitFlags([], ['A'])).toEqual([])
  })
  it('turns calibration bins into chart points and tolerates none', () => {
    expect(calibrationPoints([{ mean_predicted: 0.3, observed_rate: 0.25, n: 40 }])).toEqual([{ x: 0.3, y: 0.25, n: 40 }])
    expect(calibrationPoints(undefined)).toEqual([])
  })
  it('summarises in plain language and says nothing for an empty summary', () => {
    const lines = summaryLines({ races: 14, winner_in_predicted_top3: 13, winners_scored: 14, mean_p_win_given_to_winner: 0.47, mean_chance_level_p_win: 0.045 })
    expect(lines[0]).toBe('13 of 14 winners were in the predicted top three')
    expect(lines[1]).toContain('47% on average')
    expect(lines[1]).toContain('by pure chance')
    expect(summaryLines({ races: 0 })).toEqual([])
    expect(summaryLines(undefined)).toEqual([])
  })
})

describe('TrackRecordView', () => {
  const race = (round, mode) => ({
    round, event: `Test Grand Prix ${round}`, mode, winner: 'AAA', winner_p_win: 0.61, predicted_top3: ['AAA', 'BBB', 'CCC'],
    actual_top3: ['AAA', 'CCC', 'DDD'], spearman: 0.7, mean_position_error: 3.2, forecast_saved_at: null,
  })
  const summary = {
    races: 2, winner_in_predicted_top3: 2, winners_scored: 2, winner_predicted_first: 1, mean_p_win_given_to_winner: 0.5,
    mean_chance_level_p_win: 0.05, mean_spearman: 0.7, mean_position_error: 3.2, mean_podium_overlap: 2,
  }
  const base = {
    year: 2026, modes: ['pre-qualifying', 'post-qualifying'],
    races: [race(5, 'pre-qualifying'), race(5, 'post-qualifying'), race(6, 'post-qualifying')],
    summary: { 'pre-qualifying': { ...summary, races: 1 }, 'post-qualifying': summary },
    calibration: { 'post-qualifying': { podium: [{ mean_predicted: 0.3, observed_rate: 0.3, n: 20 }] } }, pending: [],
  }

  it('replay: shows the warning note, defaults to post-qualifying and lists only that mode', () => {
    render(<TrackRecordView data={{ ...base, source: 'replay', note: 'Retrospective replay, NOT frozen: optimistic.' }} />)
    expect(screen.getByRole('note')).toHaveTextContent('NOT frozen')
    expect(screen.getByRole('note')).toHaveClass('warn')
    expect(screen.getByRole('button', { name: 'Post-qualifying', pressed: true })).toBeInTheDocument()
    const dataRows = screen.getAllByRole('row').filter((r) => /^\d/.test(r.textContent))   // header row starts with "Rd"
    expect(dataRows).toHaveLength(2)
    expect(dataRows[0].textContent).toContain('Test 5')                                      // " Grand Prix" is trimmed in the table
    expect(screen.getAllByText('AAA ✓', { exact: false }).length).toBeGreaterThan(0)   // podium hits are marked
  })

  it('saved forecasts with nothing scored yet: explains and lists those waiting for their race', () => {
    render(<TrackRecordView data={{
      year: 2026, source: 'frozen', note: 'Saved before each race.', modes: [], races: [], summary: {}, calibration: {},
      pending: [{ round: 19, mode: 'pre-qualifying', event: 'Mexico City Grand Prix', saved_at: '2026-10-28T10:00:00' }],
    }} />)
    expect(screen.getByText(/No saved forecast has been scored yet/)).toBeInTheDocument()
    expect(screen.getByLabelText('Saved forecasts waiting for their race')).toHaveTextContent('R19 Mexico City Grand Prix')
    expect(screen.getByRole('note')).not.toHaveClass('warn')
  })

  it('empty replay says so', () => {
    render(<TrackRecordView data={{ year: 2026, source: 'replay', note: 'n', modes: [], races: [], summary: {}, calibration: {}, pending: [] }} />)
    expect(screen.getByText('No past races to replay yet.')).toBeInTheDocument()
  })
})
