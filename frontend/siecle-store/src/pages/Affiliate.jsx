import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getAffiliate, getMe } from '../api/customer'
import AffiliatePanel from '../components/AffiliatePanel'
import LuxuryLoader from '../components/LuxuryLoader'

export default function Affiliate() {
  const [affiliate, setAffiliate] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (!me.authenticated) { navigate('/compte/connexion'); return null }
      return getAffiliate()
    }).then(d => {
      if (d) setAffiliate(d)
    }).catch(() => navigate('/compte/connexion'))
      .finally(() => setLoading(false))
  }, [navigate])

  const handleCodeCreated = (data) => {
    setAffiliate(prev => ({ ...prev, ...data }))
  }

  if (loading) return <LuxuryLoader />

  return (
    <div>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 28, fontWeight: 900, color: '#fff',
          letterSpacing: '0.04em', marginBottom: 12,
        }}
      >
        PROGRAMME PARRAINAGE
      </motion.h1>
      <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.7, marginBottom: 36 }}>
        Invitez vos proches à rejoindre SIÈCLE. Ils bénéficient d'une réduction à l'inscription,
        vous gagnez des points de fidélité pour chaque parrainage validé.
      </p>

      <AffiliatePanel affiliate={affiliate} onCodeCreated={handleCodeCreated} />

      <div style={{ marginTop: 32, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }} className="how-grid">
        {[
          { step: '01', label: 'Partagez votre code', text: 'Envoyez votre code personnel à vos amis et proches.' },
          { step: '02', label: 'Ils passent commande', text: 'Votre filleul utilise votre code et obtient 10% de réduction.' },
          { step: '03', label: 'Vous gagnez des points', text: 'Dès que la commande est validée, vous recevez 100 points.' },
        ].map((item, i) => (
          <motion.div
            key={item.step}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            style={{
              background: '#111', border: '1px solid rgba(255,255,255,0.06)',
              padding: 24, textAlign: 'center',
            }}
          >
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 36, fontWeight: 900,
              color: 'rgba(192,168,130,0.15)', lineHeight: 1, marginBottom: 14,
            }}>
              {item.step}
            </p>
            <p style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 8 }}>{item.label}</p>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', lineHeight: 1.65 }}>{item.text}</p>
          </motion.div>
        ))}
      </div>

      <style>{`
        @media (max-width: 600px) { .how-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
