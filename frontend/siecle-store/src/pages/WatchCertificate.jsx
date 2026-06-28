import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'

export default function WatchCertificate() {
  const { id } = useParams()
  const [cert, setCert] = useState(null)
  const [loading, setLoading] = useState(true)
  const printRef = useRef()

  useEffect(() => {
    const loadCert = async () => {
      try {
        const { apiGet } = await import('../api/apiClient')
        const data = await apiGet(`/api/v1/siecle/watches/certificate/${id}/`)
        setCert(data)
      } catch {
        // Demo fallback
        setCert({
          certificate_number: `SIECLE-${id}-2025`,
          customer_name: 'Propriétaire SIÈCLE',
          watch_name: 'Montre SIÈCLE Urban Noir',
          created_at: new Date().toLocaleDateString('fr-FR'),
          configuration: { case: 'Acier Noir', dial: 'Noir Mat', strap: 'Cuir Brun', hands: 'Dorées', engraving: '' },
        })
      } finally {
        setLoading(false)
      }
    }
    loadCert()
  }, [id])

  if (loading) return <div style={{ minHeight: '100vh', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>Chargement…</div>

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 100, paddingBottom: 80, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ maxWidth: 700, width: '100%', padding: '0 24px' }}>
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <h1 style={{ fontSize: 28, fontWeight: 900, color: '#fff', letterSpacing: '0.12em', marginBottom: 8 }}>CERTIFICAT SIÈCLE</h1>
            <p style={{ color: '#666', fontSize: 13 }}>Montre personnalisée authentifiée</p>
          </div>

          {/* Certificate card */}
          <motion.div ref={printRef} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: 'linear-gradient(145deg, #0d0d0d, #1a1a1a)', border: '1px solid rgba(216,199,163,0.3)', borderRadius: 24, overflow: 'hidden', boxShadow: '0 40px 80px rgba(0,0,0,0.6)' }}>
            {/* Header */}
            <div style={{ background: 'linear-gradient(90deg, #111, #1c1c0e)', padding: '32px 40px', borderBottom: '1px solid rgba(216,199,163,0.15)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 28, fontWeight: 900, letterSpacing: '0.22em', color: 'var(--siecle-beige)' }}>SIÈCLE</div>
                <div style={{ fontSize: 10, letterSpacing: '0.3em', color: '#666', marginTop: 4 }}>CERTIFICAT D'AUTHENTICITÉ</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 10, color: '#666', letterSpacing: '0.12em' }}>N°</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--siecle-beige)' }}>{cert.certificate_number}</div>
              </div>
            </div>

            {/* Body */}
            <div style={{ padding: '40px' }}>
              <div style={{ textAlign: 'center', marginBottom: 40 }}>
                <div style={{ width: 80, height: 80, borderRadius: '50%', border: '2px solid rgba(216,199,163,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px', fontSize: 36 }}>⌚</div>
                <h2 style={{ fontSize: 22, fontWeight: 900, color: '#fff', marginBottom: 6 }}>{cert.watch_name}</h2>
                <p style={{ color: '#888', fontSize: 13 }}>Édition personnalisée · Pièce unique</p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, marginBottom: 32 }}>
                {[
                  ['Propriétaire', cert.customer_name],
                  ['Date de création', cert.created_at],
                  ['Boîtier', cert.configuration?.case],
                  ['Cadran', cert.configuration?.dial],
                  ['Bracelet', cert.configuration?.strap],
                  ['Aiguilles', cert.configuration?.hands],
                  ...(cert.configuration?.engraving ? [['Gravure', cert.configuration.engraving]] : []),
                ].map(([k, v], i) => (
                  <div key={k} style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.04)', borderRight: i % 2 === 0 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
                    <div style={{ fontSize: 10, letterSpacing: '0.15em', color: '#555', marginBottom: 4, textTransform: 'uppercase' }}>{k}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#fff' }}>{v || '—'}</div>
                  </div>
                ))}
              </div>

              {/* QR */}
              <div style={{ textAlign: 'center', padding: '24px 0', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ width: 80, height: 80, background: '#fff', margin: '0 auto 12px', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: '#000', fontWeight: 700 }}>QR CODE</div>
                <div style={{ fontSize: 10, color: '#444', letterSpacing: '0.1em' }}>Scannez pour vérifier l'authenticité</div>
              </div>
            </div>

            {/* Footer */}
            <div style={{ background: 'rgba(0,0,0,0.4)', padding: '16px 40px', borderTop: '1px solid rgba(216,199,163,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: 10, color: '#444', letterSpacing: '0.1em' }}>SIÈCLE • LUXE URBAIN INCLUSIF</div>
              <div style={{ fontSize: 10, color: '#444' }}>© {new Date().getFullYear()} SIÈCLE</div>
            </div>
          </motion.div>

          <div style={{ display: 'flex', gap: 14, justifyContent: 'center', marginTop: 32 }}>
            <button onClick={() => window.print()}
              style={{ padding: '14px 28px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer' }}>
              TÉLÉCHARGER PDF
            </button>
            <a href="/montres" style={{ padding: '14px 28px', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textDecoration: 'none' }}>
              RETOUR MONTRES
            </a>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
