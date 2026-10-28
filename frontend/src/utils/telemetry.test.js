import { describe, expect, it } from 'vitest'
import {
  buildRibbon, formatDelta, formatLapTime, interp, lapDuration, speedAlongTrack, speedColor, stateAt,
} from './telemetry.js'

const samples = {
  time_s: [0, 1, 2, 4],
  x: [0, 10, 20, 40], y: [0, 0, 0, 0],
  speed_kph: [100, 200, 300, 100], throttle: [100, 100, 50, 0], brake: [0, 0, 0, 1],
  rpm: [9000, 10000, 11000, 8000], gear: [3, 4, 5, 2],
}
const distances = [0, 50, 100, 200]

describe('interp', () => {
  it('interpolates, clamps and handles empty input', () => {
    expect(interp([0, 2], [0, 10], 1)).toBe(5)
    expect(interp([0, 2], [0, 10], -5)).toBe(0)
    expect(interp([0, 2], [0, 10], 9)).toBe(10)
    expect(interp([], [], 1)).toBeNull()
  })
  it('does not turn a missing neighbour into zero', () => {
    expect(interp([0, 2], [null, 10], 1)).toBe(10)
    expect(interp([0, 2], [null, null], 1)).toBeNull()
  })
})

describe('stateAt', () => {
  it('interpolates continuous channels at lap time', () => {
    const s = stateAt(samples, distances, 1.5)
    expect(s.speed).toBe(250)
    expect(s.x).toBe(15)
    expect(s.distance).toBe(75)
    expect(s.finished).toBe(false)
  })
  it('uses the nearest sample for gear and clamps at the end', () => {
    expect(stateAt(samples, distances, 1.4).gear).toBe(4)
    const end = stateAt(samples, distances, 99)
    expect(end.finished).toBe(true)
    expect(end.x).toBe(40)
    expect(lapDuration(samples)).toBe(4)
  })
})

describe('speedColor', () => {
  it('maps low to dark and high to bright, clamping out-of-range values', () => {
    const lo = speedColor(0, 0, 100)
    const hi = speedColor(100, 0, 100)
    expect(hi[0] + hi[1] + hi[2]).toBeGreaterThan(lo[0] + lo[1] + lo[2])
    expect(speedColor(-50, 0, 100)).toEqual(lo)
    expect(speedColor(500, 0, 100)).toEqual(hi)
  })
})

describe('buildRibbon', () => {
  const n = 64
  const xs = Array.from({ length: n }, (_, i) => 100 * Math.cos((2 * Math.PI * i) / n))
  const ys = Array.from({ length: n }, (_, i) => 100 * Math.sin((2 * Math.PI * i) / n))
  it('produces a closed strip of the requested width', () => {
    const r = buildRibbon(xs, ys, 12)
    expect(r.positions.length).toBe(n * 2 * 3)
    expect(r.indices.length).toBe(n * 6)
    expect(Math.max(...r.indices)).toBe(2 * n - 1)
    // left/right edge distance equals the road width everywhere
    for (let i = 0; i < n; i++) {
      const d = Math.hypot(r.positions[i * 6] - r.positions[i * 6 + 3], r.positions[i * 6 + 2] - r.positions[i * 6 + 5])
      expect(d).toBeCloseTo(12, 3) // positions are stored as float32
    }
  })
  it('wraps the last segment back to the first point', () => {
    const r = buildRibbon(xs, ys, 12)
    const last = Array.from(r.indices.slice((n - 1) * 6, n * 6))
    expect(last).toContain(0)
    expect(last).toContain(1)
  })
  it('adds a colour per vertex when values are given and uses the scene frame (Z = -y)', () => {
    const vals = xs.map((_, i) => i)
    const r = buildRibbon(xs, ys, 12, vals, [0, n])
    expect(r.colors.length).toBe(n * 2 * 3)
    // point 16 is at angle 90deg: centreline y is +100 so scene z is about -100
    expect((r.positions[16 * 6 + 2] + r.positions[16 * 6 + 5]) / 2).toBeCloseTo(-100, 3)
  })
})

describe('speedAlongTrack', () => {
  it('samples speed by distance fraction', () => {
    const v = speedAlongTrack([0, 100, 200], [0, 100, 200], 4)
    expect(v).toEqual([0, 50, 100, 150])
  })
})

describe('formatting', () => {
  it('formats lap times and signed deltas, with an em dash for missing', () => {
    expect(formatLapTime(70.27)).toBe('1:10.270')
    expect(formatLapTime(null)).toBe('—')
    expect(formatDelta(0.1234)).toBe('+0.123 s')
    expect(formatDelta(-0.5)).toBe('−0.500 s')
    expect(formatDelta(null)).toBe('—')
  })
})
