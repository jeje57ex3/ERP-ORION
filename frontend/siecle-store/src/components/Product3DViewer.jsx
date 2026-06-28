import { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, useGLTF, Environment } from '@react-three/drei'

function Model({ url }) {
  const { scene } = useGLTF(url)
  const ref = useRef()
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.y += dt * 0.4 })
  return <primitive ref={ref} object={scene} scale={1.4} />
}

function FallbackImage({ src, alt }) {
  return (
    <img src={src} alt={alt}
      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
    />
  )
}

export default function Product3DViewer({ modelUrl, fallbackImage, alt = '' }) {
  if (!modelUrl) {
    return <FallbackImage src={fallbackImage} alt={alt} />
  }

  return (
    <div style={{ width: '100%', height: '100%', background: '#0A0A0A' }}>
      <Canvas camera={{ position: [0, 0, 3], fov: 45 }}>
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={1.2} />
        <Suspense fallback={null}>
          <Model url={modelUrl} />
          <Environment preset="studio" />
        </Suspense>
        <OrbitControls
          enablePan={false}
          minDistance={1.5}
          maxDistance={6}
          autoRotate={false}
        />
      </Canvas>
    </div>
  )
}
