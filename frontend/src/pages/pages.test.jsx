import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComingSoon from './ComingSoon.jsx'
import { profileRows, stopLaps, verdictText, verdictTone } from '../components/charts/StrategyResult.jsx'
import { LABEL_SHIFT } from '../three/DriverMarker.jsx'
import { formatPct, heatColor, modeInfo, podiumDrivers } from './Predictions.jsx'
import QueryState from '../components/common/QueryState.jsx'
import { fitFactor } from '../three/CameraControls.jsx'
import Stat from '../components/cards/Stat.jsx'
import StintTimeline from '../components/charts/StintTimeline.jsx'
import { filterSlow, formatRanges, isRaceLike, lapAnnotations, neutralKind, pivotLaps } from './RaceExplorer.jsx'
import { actualStrategy, pitLossNote, resizePitLaps, validateInputs } from './StrategyLab.jsx'

describe('pivotLaps', () => {
  it('keeps nulls out instead of plotting zero', () => {
    const laps = [
      { driver: 'AAA', lap_number: 1, lap_time_s: 90 },
      { driver: 'AAA', lap_number: 2, lap_time_s: null },
      { driver: 'BBB', lap_number: 1, lap_time_s: 91 },
      { driver: 'CCC', lap_number: 1, lap_time_s: 99 },
    ]
    expect(pivotLaps(laps, ['AAA', 'BBB'])).toEqual([{ lap: 1, AAA: 90, BBB: 91 }])
  })
})

describe('Race Explorer lap helpers', () => {
  const laps = [
    { driver: 'RUS', lap_number: 2, lap_time_s: 80 },
    { driver: 'RUS', lap_number: 6, lap_time_s: 93 },
    { driver: 'ANT', lap_number: 3, lap_time_s: 108 },
    { driver: 'ANT', lap_number: 7, lap_time_s: 79 },
    { driver: 'ANT', lap_number: 9, lap_time_s: null },
  ]
  it('treats races and sprints as continuous, everything else as separate attempts', () => {
    expect(isRaceLike('R')).toBe(true)
    expect(isRaceLike('S')).toBe(true)
    expect(isRaceLike('Q')).toBe(false)
    expect(isRaceLike('SQ')).toBe(false)
  })
  it('hides laps slower than 107% of each driver\'s own best and reports how many', () => {
    const { laps: kept, hidden } = filterSlow(laps, 1.07)
    expect(hidden).toBe(2) // RUS 93 (> 85.6) and ANT 108 (> 84.5)
    expect(kept.map((l) => `${l.driver}${l.lap_number}`)).toEqual(['RUS2', 'ANT7', 'ANT9'])
    expect(filterSlow(laps, 10).hidden).toBe(0)
  })
  it('keeps each driver\'s own best even when the other driver is much slower', () => {
    const { laps: kept } = filterSlow([
      { driver: 'A', lap_number: 1, lap_time_s: 60 }, { driver: 'B', lap_number: 1, lap_time_s: 90 },
    ], 1.07)
    expect(kept).toHaveLength(2)
  })
  it('fills gap laps with empty rows only when asked, so races show real breaks', () => {
    const race = [
      { driver: 'A', lap_number: 1, lap_time_s: 90 }, { driver: 'A', lap_number: 4, lap_time_s: 91 },
    ]
    expect(pivotLaps(race, ['A']).map((r) => r.lap)).toEqual([1, 4])
    const filled = pivotLaps(race, ['A'], { fillGaps: true })
    expect(filled.map((r) => r.lap)).toEqual([1, 2, 3, 4])
    expect(filled[1].A).toBeUndefined() // a gap, not zero
  })
})

describe('gap explanations (neutralised laps and pit stops)', () => {
  it('classifies track status: red beats safety car beats VSC, yellow alone is nothing', () => {
    expect(neutralKind('1')).toBeNull()
    expect(neutralKind('2')).toBeNull()
    expect(neutralKind('12')).toBeNull()
    expect(neutralKind('267')).toBe('vsc')
    expect(neutralKind('7')).toBe('vsc')
    expect(neutralKind('1246')).toBe('sc')
    expect(neutralKind('15')).toBe('red')
    expect(neutralKind(null)).toBeNull()
  })

  it('formats lap runs compactly', () => {
    expect(formatRanges([11, 12, 13, 14, 16, 17, 18, 19, 20, 22, 32, 33, 34])).toBe('11–14, 16–20, 22, 32–34')
    expect(formatRanges([5])).toBe('5')
    expect(formatRanges([])).toBe('')
    expect(formatRanges([3, 1, 2])).toBe('1–3')
  })

  const lap = (driver, n, extra = {}) => ({ driver, lap_number: n, lap_time_s: 85, is_valid: true, is_pit_lap: false, track_status: '1', ...extra })
  const laps = [
    // ANT pits on lap 12 (in-lap 12, out-lap 13); VSC laps 11-12 for ANT, 12-13 for RUS (boundaries differ)
    lap('ANT', 10), lap('ANT', 11, { track_status: '16', is_valid: false }),
    lap('ANT', 12, { track_status: '67', is_pit_lap: true, is_valid: false }),
    lap('ANT', 13, { is_pit_lap: true, is_valid: false }), lap('ANT', 14, { track_status: '12' }),
    lap('RUS', 12, { track_status: '6', is_valid: false }), lap('RUS', 13, { track_status: '7', is_valid: false }),
    lap('RUS', 1, { is_pit_lap: true, is_valid: false }),   // pit-lane start, not a stop
    lap('LEC', 12, { track_status: '4', is_valid: false }), // not selected: must be ignored
  ]

  it('merges consecutive neutralised laps across the selected drivers into one band', () => {
    const { bands } = lapAnnotations(laps, ['ANT', 'RUS'])
    expect(bands).toEqual([{ kind: 'vsc', from: 11, to: 13 }])
  })

  it('takes the worst condition when drivers disagree, and ignores unselected drivers', () => {
    expect(lapAnnotations(laps, ['ANT']).bands).toEqual([{ kind: 'vsc', from: 11, to: 12 }])
    const withSc = lapAnnotations(laps, ['ANT', 'LEC']).bands
    expect(withSc).toEqual([{ kind: 'vsc', from: 11, to: 11 }, { kind: 'sc', from: 12, to: 12 }])
  })

  it('does not shade yellow-only laps', () => {
    expect(lapAnnotations([lap('ANT', 5, { track_status: '12' })], ['ANT']).bands).toEqual([])
  })

  it('marks one stop per pit-lap run at the in-lap, and ignores a lone lap-1 pit lap', () => {
    const { pits } = lapAnnotations(laps, ['ANT', 'RUS'])
    expect(pits).toEqual([{ driver: 'ANT', lap: 12 }])
  })

  it('pivot skips invalid laps now that the API returns every lap, but accepts missing flags', () => {
    const rows = pivotLaps([lap('ANT', 11, { is_valid: false }), lap('ANT', 10)], ['ANT'])
    expect(rows).toEqual([{ lap: 10, ANT: 85 }])
    expect(pivotLaps([{ driver: 'ANT', lap_number: 1, lap_time_s: 90 }], ['ANT'])).toHaveLength(1)
  })

  it('slow-lap filter ignores invalid laps when finding the best lap', () => {
    const { laps: kept } = filterSlow([lap('ANT', 1, { lap_time_s: 50, is_valid: false }), lap('ANT', 2, { lap_time_s: 80 })], 1.07)
    expect(kept.map((l) => l.lap_number)).toContain(2)
  })
})

describe('validateInputs', () => {
  it('accepts a legal one-stop', () => {
    expect(validateInputs({ compounds: ['MEDIUM', 'HARD'], pitLaps: [20] })).toEqual([])
  })
  it('rejects same compound, mismatched counts and non-increasing laps', () => {
    expect(validateInputs({ compounds: ['HARD', 'HARD'], pitLaps: [20] })).not.toEqual([])
    expect(validateInputs({ compounds: ['HARD', 'SOFT'], pitLaps: [] })).not.toEqual([])
    expect(validateInputs({ compounds: ['HARD', 'SOFT', 'MEDIUM'], pitLaps: [20, 10] })).not.toEqual([])
  })
})

describe('fitFactor', () => {
  it('leaves landscape canvases alone and pulls the camera back for portrait ones', () => {
    expect(fitFactor(1.6)).toBe(1)
    expect(fitFactor(0.5)).toBeCloseTo(2.3, 5)
    expect(fitFactor(0)).toBeGreaterThan(1)   // degenerate size must not divide by zero
    expect(Number.isFinite(fitFactor(0))).toBe(true)
  })
})

describe('QueryState', () => {
  const render_ = (query) => render(<QueryState query={query}>{(d) => <p>got {d.value}</p>}</QueryState>)
  it('shows loading for a disabled query with no data instead of crashing', () => {
    render_({ isLoading: false, isError: false, data: undefined })
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
  })
  it('shows errors and data', () => {
    render_({ isLoading: false, isError: true, error: new Error('boom') })
    expect(screen.getByRole('alert')).toHaveTextContent('boom')
    render_({ isLoading: false, isError: false, data: { value: 5 } })
    expect(screen.getByText('got 5')).toBeInTheDocument()
  })
})

describe('Stat', () => {
  it('shows an em dash for null, never zero', () => {
    render(<Stat label="Avg grid" value={null} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })
  it('formats decimals and keeps integers', () => {
    render(<><Stat label="A" value={3.456} digits={1} /><Stat label="B" value={7} /></>)
    expect(screen.getByText('3.5')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })
})

describe('StintTimeline', () => {
  it('labels compounds with letters and an accessible description', () => {
    render(<StintTimeline stints={[
      { stint: 1, compound: 'MEDIUM', start_lap: 1, end_lap: 20 },
      { stint: 2, compound: 'HARD', start_lap: 21, end_lap: 50 },
    ]} />)
    expect(screen.getByText('M')).toBeInTheDocument()
    expect(screen.getByText('H')).toBeInTheDocument()
    expect(screen.getByRole('img')).toHaveAccessibleName(/MEDIUM laps 1-20, HARD laps 21-50/)
  })
  it('handles missing stint data', () => {
    render(<StintTimeline stints={[]} />)
    expect(screen.getByText('no stint data')).toBeInTheDocument()
  })
})

describe('Strategy Lab helpers', () => {
  const lap = (n, stint, compound) => ({ lap_number: n, stint, compound })
  const laps = [
    ...Array.from({ length: 18 }, (_, i) => lap(i + 1, 1, 'medium')),
    ...Array.from({ length: 20 }, (_, i) => lap(i + 19, 2, 'HARD')),
    ...Array.from({ length: 18 }, (_, i) => lap(i + 39, 3, 'MEDIUM')),
  ]
  it('rebuilds the real strategy from stored laps: compounds, stop laps and race length', () => {
    const a = actualStrategy(laps)
    expect(a.compounds).toEqual(['MEDIUM', 'HARD', 'MEDIUM'])
    expect(a.pitLaps).toEqual([18, 38])
    expect(a.totalLaps).toBe(56)
    expect(a.stints[1]).toMatchObject({ start: 19, end: 38 })
  })
  it('copes with no laps or missing stint data', () => {
    expect(actualStrategy([])).toMatchObject({ compounds: [], pitLaps: [], totalLaps: 0 })
    expect(actualStrategy([{ lap_number: 1, stint: null, compound: null }]).stints).toEqual([])
  })
  it('keeps existing pit laps when adding a stop and spreads new ones, always increasing', () => {
    expect(resizePitLaps(['22'], 2, 56)).toEqual(['22', '37'])
    expect(resizePitLaps(['18', '38', '50'], 2, 56)).toEqual(['18', '38'])
    const added = resizePitLaps(['40'], 3, 56).map(Number)
    expect(added[0]).toBe(40)
    expect(added[1]).toBeGreaterThan(added[0])
    expect(added[2]).toBeGreaterThan(added[1])
  })
  it('explains exactly what is wrong using the race length', () => {
    const base = { compounds: ['MEDIUM', 'HARD', 'SOFT'], totalLaps: 56 }
    expect(validateInputs({ ...base, pitLaps: [22] })[0]).toMatch(/one more compound/)
    expect(validateInputs({ ...base, pitLaps: [18, 38], totalLaps: 56 })).toEqual([])
    expect(validateInputs({ ...base, pitLaps: [18, NaN] })[0]).toMatch(/whole lap number/)
    expect(validateInputs({ ...base, pitLaps: [18, 56] })[0]).toMatch(/before the last lap/)
    expect(validateInputs({ ...base, pitLaps: [18, 19] })[0]).toMatch(/at least 3 laps/)
    expect(validateInputs({ ...base, pitLaps: [38, 18] })[0]).toMatch(/increasing/)
  })
})

describe('pitLossNote', () => {
  it('distinguishes a measured pit loss from a typical default', () => {
    expect(pitLossNote({ pit_loss_seconds: 22.34, pit_loss_source: 'measured', pit_loss_stops: 9 }))
      .toBe('Pit loss used: 22.3 s, measured from 9 clean stops in this race.')
    expect(pitLossNote({ pit_loss_seconds: 22, pit_loss_source: 'default', pit_loss_stops: 2 }))
      .toMatch(/typical value/)
    expect(pitLossNote({ pit_loss_seconds: 22 })).toBe('Pit loss used: 22.0 s.')
    expect(pitLossNote({ pit_loss_seconds: null })).toBe('')
  })
})

describe('strategy result helpers', () => {
  it('builds chart rows with a band centred on the running difference', () => {
    const rows = profileRows([
      { lap: 1, actual_pace_s: 90, candidate_pace_s: 91, cumulative_delta_s: 1, band_s: 2 },
      { lap: 2, actual_pace_s: 90.1, candidate_pace_s: 90.5, cumulative_delta_s: 1.4, band_s: 2.8 },
    ])
    expect(rows[0]).toEqual({ lap: 1, delta: 1, band: [-1, 3], actual: 90, whatIf: 91 })
    expect(rows[1].band).toEqual([1.4 - 2.8, 1.4 + 2.8])
  })
  it('puts a stop at the end of every stint but the last', () => {
    expect(stopLaps([{ end_lap: 18 }, { end_lap: 38 }, { end_lap: 56 }])).toEqual([18, 38])
    expect(stopLaps([{ end_lap: 56 }])).toEqual([])
    expect(stopLaps([])).toEqual([])
  })
  it('colours the headline only when the interval excludes zero', () => {
    const r = (lo, hi) => ({ uncertainty_interval_seconds: [lo, hi] })
    expect(verdictTone(r(-20, -5))).toBe('good')
    expect(verdictTone(r(3, 14))).toBe('bad')
    expect(verdictTone(r(-8.9, 32.1))).toBe('neutral')
    expect(verdictTone(r(-1, 0))).toBe('neutral')
  })
  it('words the verdict by direction and flags results inside the uncertainty', () => {
    const r = (d, lo, hi) => ({ baseline_delta_seconds: d, uncertainty_interval_seconds: [lo, hi] })
    expect(verdictText(r(-12.3, -20, -5))).toBe('The what-if is estimated 12.3 s faster than the actual strategy.')
    expect(verdictText(r(8, 3, 14))).toBe('The what-if is estimated 8.0 s slower than the actual strategy.')
    expect(verdictText(r(11.9, -8.9, 32.1))).toMatch(/slower than the actual strategy, but this is within the model's uncertainty\.$/)
    expect(verdictText(r(0, -3, 3))).toMatch(/the same as/)
    expect(verdictText({ baseline_delta_seconds: null })).toBe('')
  })
})

describe('driver marker labels', () => {
  it('pushes the two labels to opposite sides so they cannot overlap', () => {
    expect(LABEL_SHIFT.left).toContain('-')
    expect(LABEL_SHIFT.right).not.toContain('-')
    expect(LABEL_SHIFT.left.replace('-', '')).toBe(LABEL_SHIFT.right)
  })
})

describe('prediction helpers', () => {
  it('never shows a small non-zero probability as 0%', () => {
    expect(formatPct(0.0004)).toBe('<1%')
    expect(formatPct(0)).toBe('0%')
    expect(formatPct(0.283)).toBe('28%')
    expect(formatPct(1)).toBe('100%')
    expect(formatPct(null)).toBe('—')
  })
  it('heat colour opacity rises with probability and stays in range', () => {
    const a = (p) => Number(heatColor(p).match(/, ([0-9.]+)\)$/)[1])
    expect(a(0)).toBe(0)
    expect(a(0.25)).toBeCloseTo(0.5, 2)
    expect(a(0.04)).toBeGreaterThan(0.15)   // small values stay visible
    expect(a(1)).toBe(1)
    expect(a(3)).toBe(1)                    // clamped
    expect(a(-1)).toBe(0)
  })
  it('describes the forecast mode, defaulting to pre-qualifying for anything unknown', () => {
    expect(modeInfo('post-qualifying').label).toBe('Post-qualifying')
    expect(modeInfo('post-qualifying').model).toBe('Form + grid')
    expect(modeInfo('pre-qualifying').label).toBe('Pre-qualifying')
    expect(modeInfo(undefined).label).toBe('Pre-qualifying')
  })
  it('podium is the three lowest predicted ranks in order', () => {
    const f = { drivers: [{ driver: 'C', predicted_rank: 3 }, { driver: 'A', predicted_rank: 1 }, { driver: 'D', predicted_rank: 4 }, { driver: 'B', predicted_rank: 2 }] }
    expect(podiumDrivers(f).map((d) => d.driver)).toEqual(['A', 'B', 'C'])
  })
})

describe('ComingSoon', () => {
  it('renders title and note', () => {
    render(<ComingSoon title="Circuit Lab" note="bonus" />)
    expect(screen.getByRole('heading', { name: 'Circuit Lab' })).toBeInTheDocument()
  })
})
