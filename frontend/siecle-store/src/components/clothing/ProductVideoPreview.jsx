import { useState, useRef } from 'react'
import { motion } from 'framer-motion'

export default function ProductVideoPreview({ videoUrl, poster }) {
  const [playing, setPlaying] = useState(false)
  const ref = useRef()

  const toggle = () => {
    if (playing) { ref.current?.pause(); setPlaying(false) }
    else { ref.current?.play(); setPlaying(true) }
  }

  if (!videoUrl) return null

  return (
    <div style={{ position: 'relative', borderRadius: 16, overflow: 'hidden', background: '#000', cursor: 'pointer' }} onClick={toggle}>
      <video ref={ref} src={videoUrl} poster={poster} style={{ width: '100%', display: 'block', borderRadius: 16 }} loop playsInline onEnded={() => setPlaying(false)} />
      {!playing && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.35)' }}>
          <motion.div whileHover={{ scale: 1.1 }}
            style={{ width: 60, height: 60, borderRadius: '50%', background: 'rgba(255,255,255,0.15)', border: '2px solid rgba(255,255,255,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
            <div style={{ width: 0, height: 0, borderTop: '10px solid transparent', borderBottom: '10px solid transparent', borderLeft: '18px solid #fff', marginLeft: 4 }} />
          </motion.div>
        </motion.div>
      )}
      <div style={{ position: 'absolute', bottom: 12, left: 12, fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: 'rgba(255,255,255,0.7)', background: 'rgba(0,0,0,0.4)', padding: '4px 10px', borderRadius: 999, backdropFilter: 'blur(4px)' }}>
        {playing ? '▐▐ PAUSE' : '▶ VIDÉO PRODUIT'}
      </div>
    </div>
  )
}
