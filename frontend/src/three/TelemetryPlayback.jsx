import { useCallback, useEffect, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'

export const RATES = [0.25, 0.5, 1, 2, 4]

/**
 * Playback clock for a lap replay. The authoritative time lives in a ref so the 3D scene can
 * read it every frame without re-rendering React; `displayTime` is a throttled copy for the UI.
 */
export function usePlayback(duration) {
  const timeRef = useRef(0)
  const playingRef = useRef(false)
  const rateRef = useRef(1)
  const lastUi = useRef(0)
  const [playing, setPlaying] = useState(false)
  const [rate, setRateState] = useState(1)
  const [displayTime, setDisplayTime] = useState(0)

  const pause = useCallback(() => {
    playingRef.current = false
    setPlaying(false)
  }, [])

  const seek = useCallback((t) => {
    timeRef.current = Math.min(Math.max(t, 0), duration)
    setDisplayTime(timeRef.current)
  }, [duration])

  const play = useCallback(() => {
    if (timeRef.current >= duration) seek(0) // replay from the start after finishing
    playingRef.current = true
    setPlaying(true)
  }, [duration, seek])

  const restart = useCallback(() => {
    seek(0)
    playingRef.current = true
    setPlaying(true)
  }, [seek])

  const setRate = useCallback((r) => {
    rateRef.current = r
    setRateState(r)
  }, [])

  const toggle = useCallback(() => (playingRef.current ? pause() : play()), [pause, play])

  /** Advance by dt wall-clock seconds; called every frame from <PlaybackTicker/>. */
  const tick = useCallback((dt) => {
    if (!playingRef.current) return
    timeRef.current = Math.min(timeRef.current + dt * rateRef.current, duration)
    const now = performance.now()
    if (now - lastUi.current > 50 || timeRef.current >= duration) {
      lastUi.current = now
      setDisplayTime(timeRef.current)
    }
    if (timeRef.current >= duration) pause()
  }, [duration, pause])

  // New lap data: back to the start, stopped.
  useEffect(() => {
    timeRef.current = 0
    playingRef.current = false
    setPlaying(false)
    setDisplayTime(0)
  }, [duration])

  return { timeRef, duration, playing, rate, displayTime, play, pause, toggle, restart, seek, setRate, tick }
}

/** Must be rendered inside <Canvas>. Drives the playback clock from the render loop. */
export function PlaybackTicker({ playback }) {
  useFrame((_, dt) => playback.tick(Math.min(dt, 0.1))) // cap dt so a stalled tab does not jump ahead
  return null
}

const fmt = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(2).padStart(5, '0')}`

/** DOM controls (outside the canvas). */
export function PlaybackControls({ playback }) {
  const { playing, toggle, restart, rate, setRate, displayTime, duration, seek } = playback
  return (
    <div className="playback" role="group" aria-label="Playback controls">
      <button type="button" onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
        {playing ? 'Pause' : 'Play'}
      </button>
      <button type="button" onClick={restart} aria-label="Restart">Restart</button>
      <label>
        Speed
        <select value={rate} onChange={(e) => setRate(Number(e.target.value))} aria-label="Playback speed">
          {RATES.map((r) => <option key={r} value={r}>{r}×</option>)}
        </select>
      </label>
      <input
        type="range" min={0} max={duration} step={0.01} value={displayTime}
        onChange={(e) => seek(Number(e.target.value))} aria-label="Playback position"
      />
      <span className="mono" aria-live="off">{fmt(displayTime)} / {fmt(duration)}</span>
    </div>
  )
}
