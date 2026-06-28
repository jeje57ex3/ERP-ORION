import { motion } from 'framer-motion'

const SPECS = [
  { key: 'price',        label: 'Prix',             fmt: v => `${v} €` },
  { key: 'material',     label: 'Boîtier',          fmt: v => v },
  { key: 'dial_color',   label: 'Cadran',           fmt: v => v },
  { key: 'strap',        label: 'Bracelet',         fmt: v => v },
  { key: 'movement',     label: 'Mouvement',        fmt: v => v },
  { key: 'diameter',     label: 'Diamètre',         fmt: v => v },
  { key: 'customizable', label: 'Personnalisable',  fmt: v => v ? 'Oui ✓' : 'Non' },
]

export default function WatchComparePanel({ watchA, watchB, onAdd }) {
  if (!watchA && !watchB) return null

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            <th style={{ padding: '14px 18px', textAlign: 'left', color: '#555', fontSize: 10, letterSpacing: '0.14em', borderBottom: '1px solid rgba(255,255,255,0.06)', width: '30%' }}>CRITÈRE</th>
            {[watchA, watchB].map((w, i) => (
              <th key={i} style={{ padding: '14px 18px', color: w ? '#fff' : '#333', fontWeight: 800, textAlign: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: 14 }}>
                {w?.name || '—'}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {SPECS.map((spec, i) => {
            const va = watchA?.[spec.key]
            const vb = watchB?.[spec.key]
            const better = spec.key === 'price' ? (va !== undefined && vb !== undefined ? (va < vb ? 'A' : va > vb ? 'B' : null) : null) : null
            return (
              <tr key={spec.key} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                <td style={{ padding: '12px 18px', color: '#777', fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{spec.label}</td>
                {[watchA, watchB].map((w, j) => {
                  const val = w?.[spec.key]
                  const isBetter = (j === 0 && better === 'A') || (j === 1 && better === 'B')
                  return (
                    <td key={j} style={{ padding: '12px 18px', textAlign: 'center', color: val !== undefined ? '#fff' : '#333', fontWeight: 600 }}>
                      {val !== undefined ? (
                        <span style={{ color: isBetter ? '#48C78E' : undefined }}>{spec.fmt(val)}</span>
                      ) : '—'}
                    </td>
                  )
                })}
              </tr>
            )
          })}
          <tr>
            <td />
            {[watchA, watchB].map((w, i) => (
              <td key={i} style={{ padding: '16px 18px', textAlign: 'center' }}>
                {w && <button onClick={() => onAdd?.(w)} style={{ padding: '10px 20px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 11, fontWeight: 800, cursor: 'pointer', letterSpacing: '0.12em' }}>CHOISIR</button>}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </motion.div>
  )
}
