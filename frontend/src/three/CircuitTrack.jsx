import { useMemo } from 'react'
import { Html } from '@react-three/drei'
import { BufferAttribute, BufferGeometry, DoubleSide } from 'three'
import { buildRibbon, speedAlongTrack, toScene } from '../utils/telemetry.js'

/** Road surface: ribbon along the reconstructed centreline, optionally coloured by speed. */
export default function CircuitTrack({ track, speeds, distances, colorBySpeed, speedRange, showCorners, markers }) {
  const width = Math.max(10, track.extent_m / 90) // visible at any circuit size; not the real width

  const geometry = useMemo(() => {
    const vals = colorBySpeed && speeds ? speedAlongTrack(distances, speeds, track.x.length) : null
    const r = buildRibbon(track.x, track.y, width, vals, speedRange)
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(r.positions, 3))
    if (r.colors) g.setAttribute('color', new BufferAttribute(r.colors, 3))
    g.setIndex(new BufferAttribute(r.indices, 1))
    g.computeVertexNormals()
    return g
  }, [track, speeds, distances, colorBySpeed, speedRange, width])

  const startFinish = toScene(track.x[0], track.y[0], 0.4)
  const labelStyle = { color: '#fff', background: 'rgba(0,0,0,.65)', padding: '1px 5px', borderRadius: 3, fontSize: 11, whiteSpace: 'nowrap' }

  return (
    <group>
      <mesh geometry={geometry}>
        <meshStandardMaterial vertexColors={colorBySpeed && !!speeds} color={colorBySpeed && speeds ? '#fff' : '#5b5b66'}
          side={DoubleSide} roughness={0.9} />
      </mesh>
      <mesh position={startFinish}>
        <boxGeometry args={[width * 1.4, 0.6, width * 0.35]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
      <Html position={[startFinish[0], 2, startFinish[2]]} center zIndexRange={[10, 0]}>
        <span style={{ ...labelStyle, display: 'inline-block', transform: 'translateY(26px)', opacity: 0.85 }}>Start / finish</span>
      </Html>
      {markers?.sectors?.map((s) => (
        <group key={s.label} position={toScene(s.x, s.y, 0.4)}>
          <mesh><boxGeometry args={[width * 1.2, 0.6, width * 0.2]} /><meshStandardMaterial color="#ffd24d" /></mesh>
          <Html position={[0, 14, 0]} center zIndexRange={[10, 0]}><span style={labelStyle}>{s.label}</span></Html>
        </group>
      ))}
      {showCorners && markers?.corners?.map((c) => (
        <Html key={c.label} position={toScene(c.x, c.y, 4)} center zIndexRange={[5, 0]}>
          <span style={{ ...labelStyle, background: 'rgba(40,40,60,.8)' }} title={`Speed minimum ${c.min_speed_kph.toFixed(0)} km/h`}>
            {c.label}
          </span>
        </Html>
      ))}
    </group>
  )
}
