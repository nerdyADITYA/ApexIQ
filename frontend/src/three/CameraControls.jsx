import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

export const CAMERA_PRESETS = {
  top: (r) => [0, r * 1.25, 0.001],
  angled: (r) => [r * 0.45, r * 0.7, r * 0.8],
}

/** Pull the camera back on tall (portrait) canvases so the whole circuit stays in frame. */
export const fitFactor = (aspect) => Math.max(1, 1.15 / Math.max(aspect, 0.2))

/** Orbit / zoom / pan, plus named camera presets scaled to the circuit size and canvas shape. */
export default function CameraControls({ preset, extent }) {
  const { camera, gl, size } = useThree()
  const aspect = size.width / Math.max(size.height, 1)
  const k = fitFactor(aspect)

  useEffect(() => {
    const pos = CAMERA_PRESETS[preset](extent).map((v) => v * k)
    camera.position.set(...pos)
    camera.near = 1
    camera.far = extent * 20
    camera.lookAt(0, 0, 0)
    camera.updateProjectionMatrix()
  }, [preset, extent, camera, k])

  // On touch screens let a vertical swipe scroll the page instead of being captured by the canvas.
  // Horizontal drags still orbit, and two-finger pinch / drag still zoom / pan.
  useEffect(() => {
    if (window.matchMedia?.('(pointer: coarse)').matches) gl.domElement.style.touchAction = 'pan-y'
  }, [gl])

  return (
    <OrbitControls makeDefault enableDamping dampingFactor={0.12} target={[0, 0, 0]}
      minDistance={extent * 0.2} maxDistance={extent * 6 * k} maxPolarAngle={Math.PI / 2 - 0.02} />
  )
}
