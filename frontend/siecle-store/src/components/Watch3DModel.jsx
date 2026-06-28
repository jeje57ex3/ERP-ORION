import { useEffect, useRef, Suspense, Component } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Environment, ContactShadows, useGLTF } from '@react-three/drei'
import { applyMaterialToMesh } from '../utils/watchMaterials'
import { getOption } from '../data/watchCustomizationOptions'

// ──────────────────────────────────────────────
// Animated GLB model with material application
// ──────────────────────────────────────────────
function WatchMesh({ modelUrl, customization }) {
  const { scene } = useGLTF(modelUrl)
  const groupRef = useRef()

  // Slow auto-rotation until the user grabs it
  useFrame((_, delta) => {
    if (groupRef.current) groupRef.current.rotation.y += delta * 0.18
  })

  useEffect(() => {
    if (!scene) return
    scene.traverse(child => {
      if (!child.isMesh) return
      const name = child.name.toLowerCase()

      if (name.includes('case') || name.includes('boitier') || name.includes('body')) {
        applyMaterialToMesh(child, getOption('case', customization.case))
      } else if (name.includes('dial') || name.includes('cadran') || name.includes('face')) {
        applyMaterialToMesh(child, getOption('dial', customization.dial))
      } else if (name.includes('hand') || name.includes('aiguille')) {
        applyMaterialToMesh(child, getOption('hands', customization.hands))
      } else if (name.includes('strap') || name.includes('bracelet') || name.includes('band')) {
        applyMaterialToMesh(child, getOption('strap', customization.strap))
      }
    })
  }, [scene, customization])

  return (
    <group ref={groupRef} scale={[4, 4, 4]} position={[0, -0.5, 0]}>
      <primitive object={scene} />
    </group>
  )
}

// ──────────────────────────────────────────────
// SVG fallback watch (procedural, no texture needed)
// ──────────────────────────────────────────────
function WatchSVGFallback({ customization }) {
  const caseOpt  = getOption('case',  customization.case)
  const dialOpt  = getOption('dial',  customization.dial)
  const handsOpt = getOption('hands', customization.hands)
  const strapOpt = getOption('strap', customization.strap)

  const caseColor  = caseOpt?.color  || '#1A1A1A'
  const dialColor  = dialOpt?.color  || '#080808'
  const handsColor = handsOpt?.color || '#D8C7A3'
  const strapColor = strapOpt?.color || '#050505'

  // Adjust text color for light dials
  const dialBrightness = parseInt(dialColor.replace('#',''), 16)
  const textOnDial = dialBrightness > 0x888888 ? 'rgba(0,0,0,0.6)' : 'rgba(200,200,200,0.5)'

  return (
    <svg className="watch-3d-fallback-svg" viewBox="0 0 200 364" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Top strap */}
      <rect x="66" y="4" width="68" height="72" rx="8" fill={strapColor}/>
      <circle cx="100" cy="30" r="3" fill="rgba(0,0,0,0.3)"/>
      <circle cx="100" cy="44" r="3" fill="rgba(0,0,0,0.3)"/>
      <circle cx="100" cy="58" r="3" fill="rgba(0,0,0,0.3)"/>

      {/* Top lugs */}
      <path d="M66 68 Q46 68 40 82" stroke={caseColor} strokeWidth="16" fill="none" strokeLinecap="round"/>
      <path d="M134 68 Q154 68 160 82" stroke={caseColor} strokeWidth="16" fill="none" strokeLinecap="round"/>

      {/* Case */}
      <rect x="28" y="74" width="144" height="192" rx="34" fill={caseColor}/>
      <rect x="32" y="78" width="136" height="184" rx="30" fill="rgba(0,0,0,0.25)"/>

      {/* Dial */}
      <circle cx="100" cy="170" r="70" fill={dialColor}/>
      <circle cx="100" cy="170" r="64" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1"/>

      {/* Hour markers */}
      <rect x="97" y="105" width="6" height="13" rx="2" fill={textOnDial}/>
      <rect x="155" y="167" width="13" height="6" rx="2" fill={textOnDial}/>
      <rect x="97" y="220" width="6" height="13" rx="2" fill={textOnDial}/>
      <rect x="32" y="167" width="13" height="6" rx="2" fill={textOnDial}/>

      {/* Brand text */}
      <text x="100" y="152" textAnchor="middle" fill={textOnDial} fontSize="7" letterSpacing="3.5" fontFamily="sans-serif">SIÈCLE</text>
      <line x1="80" y1="158" x2="120" y2="158" stroke={textOnDial} strokeWidth="0.5"/>

      {/* Hands (10:10 position) */}
      <line x1="100" y1="170" x2="74" y2="126" stroke={handsColor} strokeWidth="4" strokeLinecap="round"/>
      <line x1="100" y1="170" x2="124" y2="112" stroke={handsColor} strokeWidth="2.5" strokeLinecap="round"/>
      <line x1="100" y1="182" x2="100" y2="108" stroke={handsColor} strokeWidth="1" strokeLinecap="round" opacity="0.6"/>
      <circle cx="100" cy="170" r="5.5" fill={handsColor}/>
      <circle cx="100" cy="170" r="3" fill={dialColor}/>

      {/* Crown */}
      <rect x="170" y="158" width="22" height="24" rx="5" fill={caseColor} stroke="rgba(255,255,255,0.1)" strokeWidth="1"/>
      <line x1="175" y1="163" x2="175" y2="177" stroke="rgba(255,255,255,0.15)" strokeWidth="1.2"/>
      <line x1="181" y1="163" x2="181" y2="177" stroke="rgba(255,255,255,0.15)" strokeWidth="1.2"/>
      <line x1="187" y1="163" x2="187" y2="177" stroke="rgba(255,255,255,0.15)" strokeWidth="1.2"/>

      {/* Bottom lugs */}
      <path d="M66 266 Q46 272 40 282" stroke={caseColor} strokeWidth="16" fill="none" strokeLinecap="round"/>
      <path d="M134 266 Q154 272 160 282" stroke={caseColor} strokeWidth="16" fill="none" strokeLinecap="round"/>

      {/* Bottom strap */}
      <rect x="66" y="262" width="68" height="90" rx="8" fill={strapColor}/>
      <circle cx="100" cy="290" r="3" fill="rgba(0,0,0,0.3)"/>
      <circle cx="100" cy="306" r="3" fill="rgba(0,0,0,0.3)"/>
      <circle cx="100" cy="322" r="3" fill="rgba(0,0,0,0.3)"/>

      {/* Clasp */}
      <rect x="74" y="338" width="52" height="20" rx="4" fill={strapColor} stroke="rgba(255,255,255,0.08)" strokeWidth="1"/>
      <rect x="96" y="337" width="8" height="22" rx="2" fill={caseColor}/>
    </svg>
  )
}

// ──────────────────────────────────────────────
// Error boundary to catch GLTF load failures
// ──────────────────────────────────────────────
class ModelErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { failed: false } }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(err) { console.warn('[Watch3D] Model load failed:', err.message) }
  render() {
    if (this.state.failed) return this.props.fallback
    return this.props.children
  }
}

// ──────────────────────────────────────────────
// R3F scene (only rendered when model URL exists)
// ──────────────────────────────────────────────
function ThreeScene({ modelUrl, customization }) {
  return (
    <Canvas
      camera={{ position: [0, 1.2, 5], fov: 38 }}
      style={{ width: '100%', height: '100%' }}
      gl={{ antialias: true, alpha: true }}
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 8, 4]} intensity={1.2} castShadow />
      <directionalLight position={[-4, 2, -2]} intensity={0.4} color="#c8b48a" />
      <pointLight position={[0, -3, 2]} intensity={0.15} color="#d8c7a3" />

      <Suspense fallback={null}>
        <WatchMesh modelUrl={modelUrl} customization={customization} />
        <Environment preset="city" />
        <ContactShadows
          position={[0, -2.8, 0]}
          opacity={0.5}
          scale={8}
          blur={2}
          far={5}
        />
      </Suspense>

      <OrbitControls
        enablePan={false}
        minDistance={3}
        maxDistance={9}
        minPolarAngle={Math.PI * 0.1}
        maxPolarAngle={Math.PI * 0.85}
        autoRotate={false}
        target={[0, 0, 0]}
      />
    </Canvas>
  )
}

// ──────────────────────────────────────────────
// Public export — handles model vs SVG fallback
// ──────────────────────────────────────────────
export default function Watch3DModel({ modelUrl, fallbackImage, customization }) {
  const svgFallback = (
    <div className="watch-3d-fallback">
      <WatchSVGFallback customization={customization} />
      <span className="watch-3d-hint">← Sélectionnez vos options →</span>
    </div>
  )

  if (!modelUrl) return svgFallback

  return (
    <ModelErrorBoundary fallback={svgFallback}>
      <Suspense fallback={
        <div className="watch-3d-fallback">
          <WatchSVGFallback customization={customization} />
          <span className="watch-3d-hint">Chargement du modèle 3D…</span>
        </div>
      }>
        <ThreeScene modelUrl={modelUrl} customization={customization} />
      </Suspense>
    </ModelErrorBoundary>
  )
}
