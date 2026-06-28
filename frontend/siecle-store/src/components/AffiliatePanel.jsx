import { useState } from 'react'
import { motion } from 'framer-motion'
import { createAffiliateCode } from '../api/customer'

export default function AffiliatePanel({ affiliate, onCodeCreated }) {
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCreate = async () => {
    setLoading(true)
    try {
      const data = await createAffiliateCode()
      onCodeCreated?.(data)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (affiliate?.code) {
      navigator.clipboard.writeText(affiliate.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!affiliate) return null

  const { code, clicks = 0, signups = 0, orders = 0, referrals = [] } = affiliate

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Code block */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          background: '#111', border: '1px solid rgba(255,255,255,0.06)',
          padding: 32,
        }}
      >
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 20 }}>
          VOTRE CODE PARRAIN
        </p>

        {code ? (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 14,
              background: '#000', border: '1px solid rgba(192,168,130,0.2)',
              padding: '16px 20px', marginBottom: 16,
            }}>
              <span style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: 22, fontWeight: 900, letterSpacing: '0.12em', color: '#fff',
                flex: 1,
              }}>
                {code}
              </span>
              <button
                onClick={handleCopy}
                style={{
                  padding: '8px 16px',
                  background: copied ? '#C0A882' : 'transparent',
                  border: '1px solid rgba(192,168,130,0.4)',
                  color: copied ? '#000' : '#C0A882',
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                  cursor: 'pointer', transition: 'all 0.2s', whiteSpace: 'nowrap',
                }}
              >
                {copied ? 'COPIÉ !' : 'COPIER'}
              </button>
            </div>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', lineHeight: 1.7 }}>
              Partagez ce code avec vos proches. Ils bénéficient de 10% de réduction sur leur première commande,
              et vous gagnez 100 points par parrainage validé.
            </p>
          </>
        ) : (
          <div>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.4)', lineHeight: 1.7, marginBottom: 20 }}>
              Vous n'avez pas encore de code parrain. Générez-en un pour commencer à parrainer vos proches.
            </p>
            <button
              onClick={handleCreate}
              disabled={loading}
              style={{
                padding: '12px 28px',
                background: 'transparent',
                border: '1px solid rgba(192,168,130,0.5)',
                color: '#C0A882',
                fontSize: 11, fontWeight: 700, letterSpacing: '0.15em',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.5 : 1, transition: 'all 0.2s',
              }}
              onMouseEnter={e => { if (!loading) { e.currentTarget.style.background = '#C0A882'; e.currentTarget.style.color = '#000' } }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#C0A882' }}
            >
              {loading ? 'GÉNÉRATION...' : 'GÉNÉRER MON CODE'}
            </button>
          </div>
        )}
      </motion.div>

      {/* Stats */}
      {code && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {[
            { label: 'Clics', value: clicks },
            { label: 'Inscriptions', value: signups },
            { label: 'Commandes', value: orders },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              style={{
                background: '#111', border: '1px solid rgba(255,255,255,0.06)',
                padding: '20px 16px', textAlign: 'center',
              }}
            >
              <p style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: 32, fontWeight: 900, color: '#fff', lineHeight: 1,
              }}>
                {stat.value}
              </p>
              <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.14em', marginTop: 8 }}>
                {stat.label.toUpperCase()}
              </p>
            </motion.div>
          ))}
        </div>
      )}

      {/* Referrals list */}
      {referrals.length > 0 && (
        <div>
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 14 }}>
            PARRAINAGES
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {referrals.map((ref, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div>
                  <p style={{ fontSize: 13, color: '#fff' }}>{ref.referred_email}</p>
                  <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                    {ref.created_at ? new Date(ref.created_at).toLocaleDateString('fr-FR') : ''}
                  </p>
                </div>
                <span style={{
                  padding: '4px 10px',
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
                  color: ref.status === 'validated' ? '#C0A882' : 'rgba(255,255,255,0.3)',
                  border: `1px solid ${ref.status === 'validated' ? 'rgba(192,168,130,0.3)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  {ref.status === 'validated' ? 'VALIDÉ' : ref.status === 'pending' ? 'EN ATTENTE' : ref.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
