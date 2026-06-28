import { Suspense, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows, Html } from '@react-three/drei'

function WatchMesh({ color = '#1a1a1a', accent = '#D4AF37', scale = 1 }) {
  return (
    <group scale={scale}>
      <mesh castShadow position={[0, 0, 0]}>
        <cylinderGeometry args={[1.1, 1.1, 0.28, 64]} />
        <meshStandardMaterial color={color} metalness={0.9} roughness={0.15} />
      </mesh>
      <mesh position={[0, 0.16, 0]}>
        <cylinderGeometry args={[0.95, 0.95, 0.04, 64]} />
        <meshStandardMaterial color="#ffffff" transparent opacity={0.12} />
      </mesh>
      <mesh position={[0, 0.13, 0]}>
        <cylinderGeometry args={[0.9, 0.9, 0.02, 64]} />
        <meshStandardMaterial color="#111" roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.18, 0.2]}>
        <boxGeometry args={[0.04, 0.01, 0.45]} />
        <meshStandardMaterial color={accent} metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[0.22, 0.18, 0]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[0.04, 0.01, 0.6]} />
        <meshStandardMaterial color={accent} metalness={0.8} roughness={0.2} />
      </mesh>
      <mesh position={[0, 0, -0.9]}>
        <boxGeometry args={[0.6, 0.18, 1.2]} />
        <meshStandardMaterial color="#2a1a0e" roughness={0.9} />
      </mesh>
      <mesh position={[0, 0, 0.9]}>
        <boxGeometry args={[0.6, 0.18, 1.0]} />
        <meshStandardMaterial color="#2a1a0e" roughness={0.9} />
      </mesh>
    </group>
  )
}

function Loader() {
  return (
    <Html center>
      <div style={{ color: '#D8C7A3', fontSize: 11, letterSpacing: '0.2em' }}>CHARGEMENT 3D…</div>
    </Html>
  )
}

export default function WatchGalleryScene({ color, accent, autoRotate = true, height = '50vh' }) {
  return (
    <div style={{ width: '100%', height }}>
      <Canvas camera={{ position: [0, 2, 5], fov: 40 }} shadows>
        <Suspense fallback={<Loader />}>
          <ambientLight intensity={0.4} />
          <spotLight position={[5, 10, 5]} intensity={1.2} castShadow angle={0.3} penumbra={0.8} />
          <pointLight position={[-5, 5, -5]} intensity={0.4} />
          <WatchMesh color={color} accent={accent} />
          <ContactShadows position={[0, -1.6, 0]} opacity={0.5} scale={8} blur={2} far={3} />
          <Environment preset="city" />
          <OrbitControls enablePan={false} minDistance={3} maxDistance={9} autoRotate={autoRotate} autoRotateSpeed={0.8} />
        </Suspense>
      </Canvas>
    </div>
  )
}
