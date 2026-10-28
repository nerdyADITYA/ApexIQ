import { describe, expect, it } from 'vitest'
import { act, render, renderHook, screen } from '@testing-library/react'
import { PlaybackControls, usePlayback } from './TelemetryPlayback.jsx'
import { chartRows } from './TelemetryCharts.jsx'
import ErrorBoundary from '../components/common/ErrorBoundary.jsx'

describe('usePlayback', () => {
  it('starts stopped at zero and advances by dt x rate while playing', () => {
    const { result } = renderHook(() => usePlayback(10))
    act(() => result.current.tick(1)) // not playing: no movement
    expect(result.current.timeRef.current).toBe(0)
    act(() => result.current.play())
    act(() => result.current.tick(1))
    expect(result.current.timeRef.current).toBe(1)
    act(() => result.current.setRate(4))
    act(() => result.current.tick(1))
    expect(result.current.timeRef.current).toBe(5)
  })

  it('stops at the end, and play() after finishing restarts from zero', () => {
    const { result } = renderHook(() => usePlayback(3))
    act(() => result.current.play())
    act(() => result.current.tick(10))
    expect(result.current.timeRef.current).toBe(3)
    expect(result.current.playing).toBe(false)
    act(() => result.current.play())
    expect(result.current.timeRef.current).toBe(0)
    expect(result.current.playing).toBe(true)
  })

  it('pause holds the time; seek clamps to the lap; restart plays from zero', () => {
    const { result } = renderHook(() => usePlayback(10))
    act(() => result.current.play())
    act(() => result.current.tick(2))
    act(() => result.current.pause())
    act(() => result.current.tick(5))
    expect(result.current.timeRef.current).toBe(2)
    act(() => result.current.seek(99))
    expect(result.current.timeRef.current).toBe(10)
    act(() => result.current.seek(-5))
    expect(result.current.timeRef.current).toBe(0)
    act(() => result.current.seek(6))
    act(() => result.current.restart())
    expect(result.current.timeRef.current).toBe(0)
    expect(result.current.playing).toBe(true)
  })

  it('resets when the lap duration changes (new data)', () => {
    const { result, rerender } = renderHook(({ d }) => usePlayback(d), { initialProps: { d: 10 } })
    act(() => result.current.play())
    act(() => result.current.tick(4))
    rerender({ d: 20 })
    expect(result.current.timeRef.current).toBe(0)
    expect(result.current.playing).toBe(false)
  })
})

describe('PlaybackControls', () => {
  const Harness = () => {
    const pb = usePlayback(90)
    return <PlaybackControls playback={pb} />
  }
  it('toggles the play button label and exposes a labelled scrubber', () => {
    render(<Harness />)
    const btn = screen.getByRole('button', { name: 'Play' })
    act(() => btn.click())
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.getByLabelText('Playback position')).toBeInTheDocument()
    expect(screen.getByLabelText('Playback speed')).toBeInTheDocument()
    expect(screen.getByText(/0:00.00 \/ 1:30.00/)).toBeInTheDocument()
  })
})

describe('chartRows', () => {
  const base = {
    distance_m: [0, 100],
    a: { speed_kph: [100, 200], throttle: [100, 50], brake: [0, 1] },
  }
  it('builds rows for one driver, converting brake to percent and keeping nulls', () => {
    const rows = chartRows({ samples: { ...base, a: { ...base.a, brake: [null, 1] } } })
    expect(rows[0].brakeA).toBeNull()
    expect(rows[1].brakeA).toBe(100)
    expect(rows[0].speedB).toBeUndefined()
  })
  it('adds driver B and the delta when present', () => {
    const rows = chartRows({
      samples: { ...base, b: { speed_kph: [90, 190], throttle: [100, 40], brake: [0, 0] }, delta_s: [0, 0.2] },
    })
    expect(rows[1]).toMatchObject({ speedB: 190, delta: 0.2 })
  })
})

describe('ErrorBoundary', () => {
  it('shows a message instead of crashing when a child throws (e.g. no WebGL)', () => {
    const Boom = () => { throw new Error('WebGL unavailable') }
    const spy = console.error
    console.error = () => {}
    render(<ErrorBoundary message="3D view failed"><Boom /></ErrorBoundary>)
    console.error = spy
    expect(screen.getByRole('alert')).toHaveTextContent('3D view failed')
    expect(screen.getByRole('alert')).toHaveTextContent('WebGL unavailable')
  })
})
