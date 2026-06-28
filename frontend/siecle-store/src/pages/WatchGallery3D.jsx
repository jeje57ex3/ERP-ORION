import { Suspense, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows, Html } from '@react-three/drei'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'

const WATCHES = [
  { id: 1, name: 'Urban Noir', price: 289, color: '#1a1a1a', accent: '#D4AF37', desc: 'Boîtier acier, cadran noir mat, bracelet cuir' },
  { id: 2, name: 'Blanc Minéral', price: 259, color: '#f5f5f5', accent: '#C0C0C0', desc: 'Boîtier titane, cadran blanc, bracelet milanais' },
  { id: 3, name: 'Brun Élégance', price: 349, color: '#5C3A1E', accent: '#B8860B', desc: 'Boîtier bronze, cadran sable, bracelet cuir brun' },
  { id: 4, name: 'Rose Signature', price: 319, color: '#D4A0A0', accent: '#FFD700', desc: 'Boîtier plaqué or rose, cadran nude, bracelet cuir' },
]

function WatchModel({ color, accent }) {
  const group = useRef()

  return (
    <group ref={group} dispose={null}>
      {/* Case */}
      <mesh position={[0, 0, 0]} castShadow>
        <cylinderGeometry args={[1.1, 1.1, 0.28, 64]} />
        <meshStandardMaterial color={color} metalness={0.9} roughness={0.15} />
      </mesh>
      {/* Crystal */}
      <mesh position={[0, 0.16, 0]}>
        <cylinderGeometry args={[0.95, 0.95, 0.04, 64]} />
        <meshStandardMaterial color="#ffffff" transparent opacity={0.15} metalness={0} roughness={0} />
      </mesh>
      {/* Dial */}
      <mesh position={[0, 0.13, 0]}>
        <cylinderGeometry args={[0.9, 0.9, 0.02, 64]} />
        <meshStandardMaterial color="#111111" roughness={0.8} />
      </mesh>
      {/* Hour hand */}
      <mesh position={[0, 0.18, 0.2]} rotation={[0, 0, 0]}>
        <boxGeometry args={[0.04, 0.01, 0.45]} />
        <meshStandardMaterial color={accent} metalness={0.8} roughness={0.2} />
      </mesh>
      {/* Minute hand */}
      <mesh position={[0.22, 0.18, 0]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[0.04, 0.01, 0.6]} />
        <meshStandardMaterial color={accent} metalness={0.8} roughness={0.2} />
      </mesh>
      {/* Crown */}
      <mesh position={[1.2, 0, 0]}>
        <cylinderGeometry args={[0.08, 0.08, 0.2, 16]} />
        <meshStandardMaterial color={color} metalness={0.9} roughness={0.2} />
      </mesh>
      {/* Strap top */}
      <mesh position={[0, 0, -0.9]}>
        <boxGeometry args={[0.6, 0.18, 1.2]} />
        <meshStandardMaterial color="#2a1a0e" roughness={0.9} />
      </mesh>
      {/* Strap bottom */}
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
      <div style={{ color: '#D8C7A3', fontSize: 12, letterSpacing: '0.2em' }}>CHARGEMENT…</div>
    </Html>
  )
}

export default function WatchGallery3D() {
  const [active, setActive] = useState(0)
  const { addItem } = { addItem: () => {} }
  const watch = WATCHES[active]

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 80 }}>
        <div style={{ textAlign: 'center', padding: '40px 24px 0' }}>
          <div style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 14 }}>MONTRES SIÈCLE</div>
          <h1 style={{ fontSize: 'clamp(28px,5vw,52px)', fontWeight: 900, color: '#fff', letterSpacing: '0.08em', marginBottom: 8 }}>GALERIE 3D</h1>
          <p style={{ color: '#555', fontSize: 13 }}>Explorez chaque détail. Faites pivoter la montre librement.</p>
        </div>

        {/* 3D Viewer */}
        <div style={{ height: '55vh', minHeight: 380, maxHeight: 560 }}>
          <Canvas camera={{ position: [0, 2, 5], fov: 40 }} shadows>
            <Suspense fallback={<Loader />}>
              <ambientLight intensity={0.4} />
              <spotLight position={[5, 10, 5]} intensity={1.2} castShadow angle={0.3} penumbra={0.8} />
              <pointLight position={[-5, 5, -5]} intensity={0.4} />
              <WatchModel color={watch.color} accent={watch.accent} />
              <ContactShadows position={[0, -1.6, 0]} opacity={0.5} scale={8} blur={2} far={3} />
              <Environment preset="city" />
              <OrbitControls enablePan={false} minDistance={3} maxDistance={9} autoRotate autoRotateSpeed={0.8} />
            </Suspense>
          </Canvas>
        </div>

        {/* Info + selectors */}
        <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 24px 80px' }}>
          <motion.div key={active} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            style={{ textAlign: 'center', marginBottom: 40 }}>
            <h2 style={{ fontSize: 28, fontWeight: 900, color: '#fff', marginBottom: 6 }}>{watch.name}</h2>
            <p style={{ color: '#888', fontSize: 14, marginBottom: 4 }}>{watch.desc}</p>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--siecle-beige)' }}>{watch.price} €</div>
          </motion.div>

          {/* Watch selector pills */}
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 32 }}>
            {WATCHES.map((w, i) => (
              <button key={w.id} onClick={() => setActive(i)}
                style={{ padding: '10px 20px', background: i === active ? '#fff' : '#111', color: i === active ? '#000' : '#aaa', border: `1px solid ${i === active ? '#fff' : 'rgba(255,255,255,0.1)'}`, borderRadius: 999, fontSize: 12, fontWeight: 700, cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: w.color, display: 'inline-block', border: '1px solid rgba(255,255,255,0.2)' }} />
                {w.name}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
            <a href={`/montres/certificat/${watch.id}`}
              style={{ padding: '14px 28px', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', textDecoration: 'none' }}>
              VOIR CERTIFICAT
            </a>
            <button onClick={() => addItem?.({ id: watch.id, name: watch.name, price: watch.price, quantity: 1 })}
              style={{ padding: '14px 28px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.12em', cursor: 'pointer' }}>
              AJOUTER AU PANIER
            </button>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
