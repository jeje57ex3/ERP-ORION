import { motion } from 'framer-motion'

const MORPHOLOGIES = [
  { id: 'H', label: 'Rectangle', desc: 'Épaules et hanches similaires', icon: '▬' },
  { id: 'V', label: 'Triangle inversé', desc: 'Épaules plus larges', icon: '▽' },
  { id: 'A', label: 'Triangle', desc: 'Hanches plus larges', icon: '△' },
  { id: 'X', label: 'Sablier', desc: 'Taille marquée', icon: '⧖' },
  { id: 'O', label: 'Ovale', desc: 'Ventre plus large', icon: '⬭' },
]

const RECS = {
  H: ['Coupes structurées', 'Blazers cintrés', 'Pantalons slim'],
  V: ['Pantalons larges', 'Hauts fluides', 'Cols V'],
  A: ['Hauts structurés', 'Épaules marquées', 'Jupes fluides'],
  X: ['Toutes coupes', 'Ceintures soulignées', 'Robes portefeuilles'],
  O: ['Coupes droites', 'Col V allongeant', 'Matières fluides'],
}

export default function MorphologyPreview({ selected, onChange }) {
  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', color: '#888', marginBottom: 16, textTransform: 'uppercase' }}>Ma morphologie</div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        {MORPHOLOGIES.map(m => (
          <motion.button key={m.id} whileHover={{ scale: 1.04 }} onClick={() => onChange?.(m.id)}
            style={{ padding: '12px 16px', background: selected === m.id ? 'rgba(216,199,163,0.1)' : '#0d0d0d', border: `1px solid ${selected === m.id ? 'rgba(216,199,163,0.35)' : 'rgba(255,255,255,0.07)'}`, borderRadius: 12, cursor: 'pointer', textAlign: 'center', minWidth: 90, transition: 'all 0.2s' }}>
            <div style={{ fontSize: 22, marginBottom: 6 }}>{m.icon}</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: selected === m.id ? 'var(--siecle-beige)' : '#fff' }}>{m.label}</div>
            <div style={{ fontSize: 10, color: '#555', marginTop: 2 }}>{m.desc}</div>
          </motion.button>
        ))}
      </div>
      {selected && RECS[selected] && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          style={{ padding: 16, background: 'rgba(216,199,163,0.04)', border: '1px solid rgba(216,199,163,0.12)', borderRadius: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--siecle-beige)', letterSpacing: '0.12em', marginBottom: 10, fontWeight: 700 }}>RECOMMANDATIONS SIÈCLE</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {RECS[selected].map(r => (
              <li key={r} style={{ fontSize: 12, color: '#aaa', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--siecle-beige)', fontSize: 10 }}>✦</span> {r}
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  )
}
