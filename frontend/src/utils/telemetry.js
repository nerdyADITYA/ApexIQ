/** Pure helpers for telemetry playback and track geometry (no React / three.js). */

/** Linear interpolation of ys at x within a sorted xs array; clamps at both ends. null-safe. */
export function interp(xs, ys, x) {
  const n = xs.length
  if (n === 0) return null
  if (x <= xs[0]) return ys[0]
  if (x >= xs[n - 1]) return ys[n - 1]
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (xs[mid] <= x) lo = mid
    else hi = mid
  }
  const y0 = ys[lo]
  const y1 = ys[hi]
  if (y0 == null || y1 == null) return y0 ?? y1 ?? null
  const f = (x - xs[lo]) / (xs[hi] - xs[lo] || 1)
  return y0 + (y1 - y0) * f
}

/** State of one driver's lap at lap-time t (seconds). Time clamps at the lap's end. */
export function stateAt(samples, distances, t) {
  const times = samples.time_s
  const at = (ch) => interp(times, samples[ch], t)
  return {
    x: at('x'), y: at('y'), speed: at('speed_kph'), throttle: at('throttle'), brake: at('brake'),
    rpm: at('rpm'),
    gear: (() => {
      const g = samples.gear
      if (!g.length) return null
      // gear is categorical: take the nearest sample rather than interpolating between gears
      let best = 0
      for (let i = 1; i < times.length; i++) if (Math.abs(times[i] - t) < Math.abs(times[best] - t)) best = i
      return g[best]
    })(),
    distance: interp(times, distances, t),
    finished: t >= times[times.length - 1],
  }
}

export function lapDuration(samples) {
  const t = samples.time_s
  return t.length ? t[t.length - 1] : 0
}

/** Perceptually ordered dark-to-light ramp (viridis-like), value in [0,1] -> [r,g,b] in 0..1. */
const STOPS = [
  [0.267, 0.005, 0.329], [0.231, 0.322, 0.546], [0.128, 0.567, 0.551], [0.369, 0.789, 0.383], [0.993, 0.906, 0.144],
]
export function speedColor(v, min, max) {
  const f = Math.min(1, Math.max(0, (v - min) / (max - min || 1)))
  const p = f * (STOPS.length - 1)
  const i = Math.min(Math.floor(p), STOPS.length - 2)
  const k = p - i
  return STOPS[i].map((c, j) => c + (STOPS[i + 1][j] - c) * k)
}

/** Speed at each of n evenly spaced points around the lap (by distance fraction). */
export function speedAlongTrack(distances, speeds, n) {
  const total = distances[distances.length - 1]
  return Array.from({ length: n }, (_, i) => interp(distances, speeds, (i / n) * total))
}

/**
 * Flat road ribbon around a closed centreline.
 * Scene frame: X = x, Z = -y, Y up. Returns positions (3 floats/vertex), triangle indices and
 * per-vertex colours when `values` is given. Vertex 2i is the left edge, 2i+1 the right edge.
 */
export function buildRibbon(xs, ys, width, values = null, range = null) {
  const n = xs.length
  const positions = new Float32Array(n * 2 * 3)
  const colors = values ? new Float32Array(n * 2 * 3) : null
  for (let i = 0; i < n; i++) {
    const p = (i - 1 + n) % n
    const q = (i + 1) % n
    let tx = xs[q] - xs[p]
    let ty = ys[q] - ys[p]
    const len = Math.hypot(tx, ty) || 1
    tx /= len
    ty /= len
    const nx = -ty
    const ny = tx
    const hw = width / 2
    const left = [xs[i] + nx * hw, ys[i] + ny * hw]
    const right = [xs[i] - nx * hw, ys[i] - ny * hw]
    positions.set([left[0], 0, -left[1], right[0], 0, -right[1]], i * 6)
    if (colors) {
      const c = speedColor(values[i], range[0], range[1])
      colors.set([...c, ...c], i * 6)
    }
  }
  const indices = new Uint32Array(n * 6)
  for (let i = 0; i < n; i++) {
    const a = 2 * i
    const c = 2 * ((i + 1) % n)
    indices.set([a, a + 1, c, a + 1, c + 1, c], i * 6)
  }
  return { positions, indices, colors }
}

/** Scene-frame position for a track-plane (x, y). */
export const toScene = (x, y, h = 0) => [x, h, -y]

export function formatLapTime(s) {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  return `${m}:${(s - m * 60).toFixed(3).padStart(6, '0')}`
}

export function formatDelta(s) {
  if (s == null) return '—'
  return `${s >= 0 ? '+' : '−'}${Math.abs(s).toFixed(3)} s`
}
