import { Canvas } from '@react-three/fiber'
import CircuitTrack from './CircuitTrack.jsx'
import DriverMarker from './DriverMarker.jsx'
import CameraControls from './CameraControls.jsx'
import { PlaybackTicker } from './TelemetryPlayback.jsx'

export const COLOR_A = '#ff5d5d'
export const COLOR_B = '#4dc3ff'

/** The whole 3D view. Everything WebGL lives under this component. */
export default function CircuitScene({ data, playback, colorBySpeed, showCorners, cameraPreset, speedRange }) {
  const { track, samples, markers } = data
  return (
    <Canvas dpr={[1, 2]} camera={{ fov: 45 }} aria-label="3D circuit replay" role="img">
      <color attach="background" args={['#0b0b10']} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[track.extent_m, track.extent_m * 2, track.extent_m]} intensity={1.1} />
      <CircuitTrack
        track={track} speeds={samples.a.speed_kph} distances={samples.distance_m}
        colorBySpeed={colorBySpeed} speedRange={speedRange} showCorners={showCorners} markers={markers}
      />
      <DriverMarker tag="A" code={data.a.code} color={COLOR_A} shape="disc" side="left" size={track.extent_m / 55 + 6}
        samples={samples.a} distances={samples.distance_m} playback={playback} />
      {samples.b && (
        <DriverMarker tag="B" code={data.b.code} color={COLOR_B} shape="diamond" side="right" size={track.extent_m / 55 + 6}
          samples={samples.b} distances={samples.distance_m} playback={playback} />
      )}
      <CameraControls preset={cameraPreset} extent={track.extent_m} />
      <PlaybackTicker playback={playback} />
    </Canvas>
  )
}
