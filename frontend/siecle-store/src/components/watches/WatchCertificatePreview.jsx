import { motion } from 'framer-motion'

export default function WatchCertificatePreview({ cert, compact = false }) {
  if (!cert) return null

  if (compact) {
    return (
      <a href={`/montres/certificat/${cert.id || cert.certificate_number}`}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: '#0d0d0d', border: '1px solid rgba(216,199,163,0.15)', borderRadius: 12, textDecoration: 'none' }}>
        <span style={{ fontSize: 22 }}>📜</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{cert.watch_name}</div>
          <div style={{ fontSize: 11, color: '#555', letterSpacing: '0.1em' }}>N° {cert.certificate_number}</div>
        </div>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--siecle-beige)' }}>Voir →</span>
      </a>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      style={{ background: 'linear-gradient(145deg, #0d0d0d, #1a1a1a)', border: '1px solid rgba(216,199,163,0.2)', borderRadius: 16, padding: 24, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 900, letterSpacing: '0.2em', color: 'var(--siecle-beige)' }}>SIÈCLE</div>
        <div style={{ fontSize: 10, color: '#555', textAlign: 'right', letterSpacing: '0.1em' }}>N° {cert.certificate_number}</div>
      </div>
      <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', marginBottom: 4 }}>{cert.watch_name}</div>
      <div style={{ fontSize: 12, color: '#888', marginBottom: 16 }}>{cert.customer_name} · {cert.created_at}</div>
      {cert.configuration && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {Object.entries(cert.configuration).filter(([, v]) => v).map(([k, v]) => (
            <div key={k} style={{ fontSize: 11 }}>
              <span style={{ color: '#444', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{k}: </span>
              <span style={{ color: '#aaa' }}>{v}</span>
            </div>
          ))}
        </div>
      )}
      <a href={`/montres/certificat/${cert.id || cert.certificate_number}`}
        style={{ display: 'block', marginTop: 16, fontSize: 11, fontWeight: 700, color: 'var(--siecle-beige)', letterSpacing: '0.12em', textDecoration: 'none' }}>
        VOIR LE CERTIFICAT COMPLET →
      </a>
    </motion.div>
  )
}
