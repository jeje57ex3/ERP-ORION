import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

export default function SavedWatchConfiguration({ onSelect }) {
  const [configs, setConfigs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const { getConfigurations } = await import('../../api/watches')
        const data = await getConfigurations()
        setConfigs(data.results || data)
      } catch {
        setConfigs([])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div style={{ color: '#555', fontSize: 12 }}>Chargement…</div>
  if (configs.length === 0) return (
    <div style={{ textAlign: 'center', padding: 32, color: '#444', fontSize: 13 }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⌚</div>
      Aucune configuration sauvegardée.<br />
      <a href="/montres" style={{ color: 'var(--siecle-beige)', textDecoration: 'none', fontWeight: 700, fontSize: 12, letterSpacing: '0.1em' }}>Configurer une montre →</a>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {configs.map((cfg, i) => (
        <motion.div key={cfg.id || i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
          onClick={() => onSelect?.(cfg)}
          style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 14, cursor: 'pointer', transition: 'border-color 0.2s' }}>
          <div style={{ width: 48, height: 48, borderRadius: 10, background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22 }}>⌚</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{cfg.name || `Configuration ${i + 1}`}</div>
            <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>
              {[cfg.case_material, cfg.dial_color, cfg.strap].filter(Boolean).join(' · ')}
            </div>
          </div>
          <button style={{ marginLeft: 'auto', padding: '8px 16px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', color: '#aaa', borderRadius: 8, fontSize: 11, cursor: 'pointer', fontWeight: 600 }}>
            Sélectionner
          </button>
        </motion.div>
      ))}
    </div>
  )
}
