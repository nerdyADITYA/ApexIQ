import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { stateAt } from '../utils/telemetry.js'

/** Label pills are pushed to opposite sides so two cars on the same spot never overlap their labels. */
export const LABEL_SHIFT = { left: 'translateX(-62%)', right: 'translateX(62%)' }

/**
 * A car marker driven by the shared playback clock; it stops at the line when its own lap has ended.
 * Driver A is a flat disc, driver B a smaller diamond floating above, so both stay visible when they overlap
 * exactly (for example on the start line) and the two are told apart by shape as well as colour.
 */
export default function DriverMarker({ tag, code, color, shape = 'disc', side = 'left', samples, distances, playback, size = 16 }) {
  const ref = useRef()
  const lift = shape === 'disc' ? size * 0.14 : size * 0.8
  useFrame(() => {
    const s = stateAt(samples, distances, playback.timeRef.current)
    if (s.x == null || s.y == null || !ref.current) return
    ref.current.position.set(s.x, 0, -s.y)
  })
  return (
    <group ref={ref}>
      {shape === 'disc' ? (
        <>
          <mesh position={[0, lift * 0.55, 0]}>
            <cylinderGeometry args={[size * 0.74, size * 0.74, size * 0.1, 32]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
          <mesh position={[0, lift, 0]}>
            <cylinderGeometry args={[size * 0.62, size * 0.62, size * 0.18, 32]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.45} />
          </mesh>
        </>
      ) : (
        <mesh position={[0, lift, 0]}>
          <octahedronGeometry args={[size * 0.56]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.55} />
        </mesh>
      )}
      <Html position={[0, size * 2.3, 0]} center zIndexRange={[20, 0]}>
        <span
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', transform: LABEL_SHIFT[side],
            padding: '2px 9px 2px 3px', borderRadius: 999, background: 'rgba(14,16,20,.92)', color: '#fff',
            border: `1.5px solid ${color}`, fontSize: 12, fontWeight: 600, lineHeight: '18px',
          }}
        >
          <b style={{ background: color, color: '#111', borderRadius: '50%', width: 18, height: 18, textAlign: 'center', fontSize: 11 }}>{tag}</b>
          {code}
        </span>
      </Html>
    </group>
  )
}
